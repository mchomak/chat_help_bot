"""AI API client using proxy-managed HTTP requests."""

from __future__ import annotations

import json
import logging

import aiohttp

from app.config import settings
from app.proxy.manager import proxy_manager

logger = logging.getLogger(__name__)


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    has_image: bool = False,
) -> str:
    """Send chat completion request to the AI API and return raw content string.

    Uses proxy rotation for outbound requests.
    """
    chosen_model = model or (
        settings.ai.vision_model if has_image else settings.ai.default_model
    )
    url = f"{settings.ai.api_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": chosen_model,
        "messages": messages,
        "max_tokens": settings.ai.max_tokens,
        "temperature": settings.ai.temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.ai.api_key}",
        "Content-Type": "application/json",
    }
    timeout = aiohttp.ClientTimeout(total=settings.ai.request_timeout)

    resp = await proxy_manager.request_with_rotation(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
    )

    body = await resp.json()

    if resp.status != 200:
        error_msg = body.get("error", {}).get("message", str(body))
        logger.error("AI API error %d: %s", resp.status, error_msg)
        raise RuntimeError(f"AI API error {resp.status}: {error_msg}")

    content = body["choices"][0]["message"]["content"]
    return content
