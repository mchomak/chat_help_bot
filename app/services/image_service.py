"""Image download and cleanup service. Files live only during AI processing."""

from __future__ import annotations

import base64
import io
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from aiogram import Bot

logger = logging.getLogger(__name__)


@asynccontextmanager
async def download_telegram_photo(bot: Bot, file_id: str) -> AsyncIterator[bytes]:
    """Download photo to memory; yield raw bytes. No temp files needed."""
    buf = io.BytesIO()
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=buf)
    logger.debug("Downloaded file %s (%d bytes)", file_id, buf.tell())
    buf.seek(0)
    try:
        yield buf.read()
    finally:
        buf.close()


def photo_bytes_to_base64(data: bytes) -> str:
    """Encode raw bytes to base64 string."""
    return base64.b64encode(data).decode("utf-8")
