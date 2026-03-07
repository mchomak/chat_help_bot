"""Image download and cleanup service. Files live only during AI processing."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from aiogram import Bot

from app.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def download_telegram_photo(
    bot: Bot,
    file_id: str,
) -> AsyncIterator[Path]:
    """Download photo to a temp file; guaranteed cleanup on exit."""
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = settings.temp_dir / f"{uuid.uuid4().hex}.jpg"
    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=str(tmp_path))
        logger.debug("Downloaded file %s -> %s", file_id, tmp_path)
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
            logger.debug("Removed temp file %s", tmp_path)


async def photo_to_base64(path: Path) -> str:
    """Read image file and return base64-encoded string."""
    data = path.read_bytes()
    return base64.b64encode(data).decode("utf-8")
