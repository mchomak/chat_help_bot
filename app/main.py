"""Application entry point — webhook-based aiogram 3 bot."""

from __future__ import annotations

import logging

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


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]
    webhook_url = settings.bot.webhook_url
    logger.info("Setting webhook: %s", webhook_url)
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.bot.webhook_secret or None,
        drop_pending_updates=True,
    )
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
