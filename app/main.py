"""Application entry point — webhook-based aiogram 3 bot."""

from __future__ import annotations

import asyncio
import logging
import socket
from urllib.parse import urlparse

from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from app.db.session import get_session_factory

from app.bot.setup import create_bot, create_dispatcher
from app.config import settings
from app.db.session import close_engine, get_engine

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
# Suppress noisy SQLAlchemy INFO logs (connection pool, SQL echo)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


class _TLSProbeFilter(logging.Filter):
    """Drop log records caused by TLS/HTTPS connections hitting the plain-HTTP port.

    Symptom: internet scanners or misconfigured clients send TLS ClientHello bytes
    (b'\\x16\\x03\\x01...') directly to our HTTP port, producing aiohttp errors like:
      BadHttpMethod: 400, message: Invalid method encountered: b'\\x16\\x03\\x01\\x02'

    Root fix: ensure the port is only bound to 127.0.0.1 in docker-compose so it's
    never reachable from the internet without going through the reverse proxy (nginx).
    This filter handles any residual noise (e.g. local-network probes).
    """

    _SKIP_PHRASES = (
        "Invalid method encountered",   # TLS ClientHello on HTTP port
        "BadStatusLine",                # Other malformed HTTP from scanners
    )

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(phrase in msg for phrase in self._SKIP_PHRASES)


# Apply filter to aiohttp's low-level server logger (raises WARNING for bad requests)
logging.getLogger("aiohttp.server").addFilter(_TLSProbeFilter())

logger = logging.getLogger(__name__)


async def health_handler(request: web.Request) -> web.Response:
    """Liveness probe used by Docker healthcheck."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return web.json_response({"status": "ok"})
    except Exception as exc:
        return web.json_response({"status": "error", "detail": str(exc)}, status=503)


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """Receive YooKassa payment status notifications.

    We re-verify the payment status directly from the YooKassa API instead of
    trusting the webhook payload, so no additional signature check is needed.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("YooKassa webhook: could not parse JSON body")
        return web.Response(status=400)

    if body.get("type") != "notification":
        return web.Response(status=200)  # Ignore non-notification events

    event_object = body.get("object", {})
    yookassa_payment_id = event_object.get("id")

    if not yookassa_payment_id:
        logger.warning("YooKassa webhook: missing payment id in body")
        return web.Response(status=400)

    bot: Bot = request.app["bot"]
    factory = get_session_factory()

    async with factory() as session:
        from app.services.payment_service import process_webhook
        await process_webhook(session, bot, yookassa_payment_id)
        await session.commit()

    return web.Response(status=200)


async def _dns_resolves(hostname: str) -> bool:
    """Return True if hostname resolves via local DNS (non-blocking)."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, socket.getaddrinfo, hostname, None)
        return True
    except (socket.gaierror, OSError):
        return False


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    webhook_url = settings.bot.webhook_url

    # ── 1. Validate webhook URL structure ────────────────────────────────────
    parsed = urlparse(webhook_url)
    host = parsed.hostname or ""

    if not host:
        logger.critical(
            "WEBHOOK_HOST is empty or not set. "
            "Add WEBHOOK_HOST=https://yourdomain.com to .env and restart."
        )
        raise RuntimeError("WEBHOOK_HOST is not configured")

    if parsed.scheme != "https":
        logger.critical(
            "Telegram requires HTTPS for webhooks. "
            "WEBHOOK_HOST must start with 'https://'. Got: %r", webhook_url,
        )
        raise RuntimeError(f"Webhook URL must use HTTPS, got: {webhook_url!r}")

    logger.info("Setting webhook: %s", webhook_url)

    # ── 2. DNS pre-check — warn if hostname doesn't resolve locally ───────────
    # Local resolution failure is a strong signal that Telegram will also fail.
    # The most common cause with DuckDNS: the update URL was never called to
    # point the subdomain at this server's IP.
    if not await _dns_resolves(host):
        logger.warning(
            "Webhook host %r does not resolve via local DNS.\n"
            "  If using DuckDNS, update the record now:\n"
            "    curl 'https://www.duckdns.org/update?domains=<subdomain>"
            "&token=<token>&ip='\n"
            "  Then check: nslookup %s\n"
            "  Telegram will likely reject set_webhook with 'Failed to resolve host'.",
            host, host,
        )
    else:
        logger.info("DNS check passed: %r resolves OK", host)

    # ── 3. set_webhook with exponential-backoff retries ───────────────────────
    # Retries handle transient cases: container starts before DuckDNS update
    # script runs, or a brief network hiccup right after boot.
    _ATTEMPTS = 4          # total tries
    _BASE_DELAY = 2        # seconds — doubles each retry: 2, 4, 8
    last_exc: Exception | None = None

    for attempt in range(1, _ATTEMPTS + 1):
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.bot.webhook_secret or None,
                drop_pending_updates=True,
            )
            logger.info("Webhook set successfully (attempt %d/%d)", attempt, _ATTEMPTS)
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "set_webhook attempt %d/%d failed: %s", attempt, _ATTEMPTS, exc,
            )
            if attempt < _ATTEMPTS:
                delay = _BASE_DELAY ** attempt   # 2, 4, 8 s
                logger.info("Retrying in %ds...", delay)
                await asyncio.sleep(delay)
    else:
        logger.critical(
            "Failed to set Telegram webhook after %d attempts.\n"
            "  Webhook URL : %s\n"
            "  Host        : %s\n"
            "  Last error  : %s\n"
            "Checklist:\n"
            "  1. DuckDNS record updated? Call the update URL and verify with:\n"
            "       nslookup %s\n"
            "  2. nginx running and port 443 open in firewall?\n"
            "       curl -I https://%s/health\n"
            "  3. TLS certificate valid for this domain?\n"
            "       certbot certificates",
            _ATTEMPTS, webhook_url, host, last_exc, host, host,
        )
        raise RuntimeError(f"Cannot set Telegram webhook: {last_exc}") from last_exc

    # Ensure temp dir exists
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Bot started, webhook set")


async def on_shutdown(app: web.Application) -> None:
    bot: Bot = app["bot"]
    logger.info("Shutting down...")
    await bot.delete_webhook()
    await close_engine()
    logger.info("Shutdown complete")


def main() -> None:
    bot = create_bot()
    dp = create_dispatcher()

    app = web.Application()
    app["bot"] = bot

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.bot.webhook_secret or None,
    )
    webhook_handler.register(app, path=settings.bot.webhook_path)
    app.router.add_get("/health", health_handler)
    app.router.add_post(settings.yookassa.webhook_path, yookassa_webhook_handler)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Force engine creation at startup
    get_engine()

    logger.info("Starting webhook server on port %d", settings.bot.webhook_port)
    web.run_app(
        app,
        host="0.0.0.0",
        port=settings.bot.webhook_port,
    )


if __name__ == "__main__":
    main()
