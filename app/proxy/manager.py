"""Proxy manager with rotation, health tracking, cooldown, and retry logic."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProxyStats:
    url: str
    fail_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    cooldown_until: float = 0.0

    @property
    def is_cooled_down(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def record_success(self) -> None:
        self.success_count += 1
        self.fail_count = 0

    def record_failure(self) -> None:
        self.fail_count += 1
        self.last_failure_time = time.monotonic()
        if self.fail_count >= 3:
            self.cooldown_until = time.monotonic() + settings.proxy.cooldown_seconds
            logger.warning(
                "Proxy %s put on cooldown for %ds after %d consecutive failures",
                self.url, settings.proxy.cooldown_seconds, self.fail_count,
            )


class ProxyManager:
    """Manages a list of proxies with rotation and health tracking.

    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(self) -> None:
        self._proxies: list[ProxyStats] = [
            ProxyStats(url=p) for p in settings.proxy.proxies
        ]
        self._current_idx: int = 0
        self._lock = asyncio.Lock()

    @property
    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    def _get_available(self) -> list[ProxyStats]:
        return [p for p in self._proxies if p.is_cooled_down]

    async def get_next_proxy(self) -> str | None:
        """Return next available proxy URL, or None if all are on cooldown or list is empty."""
        if not self._proxies:
            return None
        async with self._lock:
            available = self._get_available()
            if not available:
                # Reset cooldowns if all proxies exhausted
                for p in self._proxies:
                    p.cooldown_until = 0.0
                available = self._proxies
                logger.warning("All proxies were on cooldown — resetting")
            proxy = available[self._current_idx % len(available)]
            self._current_idx = (self._current_idx + 1) % max(len(available), 1)
            return proxy.url

    async def report_success(self, proxy_url: str) -> None:
        for p in self._proxies:
            if p.url == proxy_url:
                p.record_success()
                return

    async def report_failure(self, proxy_url: str) -> None:
        for p in self._proxies:
            if p.url == proxy_url:
                p.record_failure()
                return

    async def request_with_rotation(
        self,
        method: str,
        url: str,
        *,
        max_retries: int | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
        **kwargs,
    ) -> aiohttp.ClientResponse:
        """Execute HTTP request with proxy rotation and retries.

        Returns the response object; caller is responsible for closing it.
        Raises the last exception if all retries are exhausted.
        """
        retries = max_retries or settings.proxy.max_retries
        if timeout is None:
            timeout = aiohttp.ClientTimeout(
                connect=settings.proxy.connect_timeout,
                total=settings.proxy.read_timeout + settings.proxy.connect_timeout,
                sock_read=settings.proxy.read_timeout,
            )

        last_exc: Exception | None = None

        for attempt in range(retries + 1):
            proxy_url = await self.get_next_proxy()
            try:
                connector = aiohttp.TCPConnector(ssl=False) if proxy_url else None
                async with aiohttp.ClientSession(
                    timeout=timeout,
                    connector=connector,
                ) as session:
                    start = time.monotonic()
                    resp = await session.request(
                        method, url, proxy=proxy_url, **kwargs,
                    )
                    elapsed = time.monotonic() - start

                    if elapsed > settings.proxy.slow_threshold and proxy_url:
                        logger.warning(
                            "Slow response (%.1fs) via proxy %s", elapsed, proxy_url,
                        )

                    if resp.status >= 500:
                        body = await resp.text()
                        if proxy_url:
                            await self.report_failure(proxy_url)
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=f"Server error {resp.status}: {body[:200]}",
                        )

                    if proxy_url:
                        await self.report_success(proxy_url)

                    # Return a new session+response that caller can consume
                    # We need to read the body here since session is closing
                    body_bytes = await resp.read()

                    class InMemoryResponse:
                        """Lightweight container holding already-fetched response data."""
                        def __init__(self, status, headers, body, content_type):
                            self.status = status
                            self.headers = headers
                            self._body = body
                            self.content_type = content_type

                        async def read(self):
                            return self._body

                        async def text(self, encoding="utf-8"):
                            return self._body.decode(encoding)

                        async def json(self, **kw):
                            import json as _json
                            return _json.loads(self._body)

                    return InMemoryResponse(
                        status=resp.status,
                        headers=resp.headers,
                        body=body_bytes,
                        content_type=resp.content_type,
                    )

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                OSError,
            ) as exc:
                last_exc = exc
                if proxy_url:
                    await self.report_failure(proxy_url)
                logger.warning(
                    "Request failed via proxy=%s: %s (attempt %d/%d)",
                    proxy_url or "direct", exc, attempt + 1, retries + 1,
                )
                if attempt < retries:
                    backoff = min(2 ** attempt, 8)
                    await asyncio.sleep(backoff)

        raise last_exc  # type: ignore[misc]


# Singleton instance
proxy_manager = ProxyManager()
