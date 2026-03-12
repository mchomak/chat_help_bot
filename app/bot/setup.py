"""Bot and dispatcher factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    analyzer,
    anti_ignor,
    cancel,
    consent,
    first_message,
    flirt,
    help as help_handler,
    menu,
    modifier,
    onboarding,
    payment,
    photo_pickup,
    settings_handler,
    start,
)
from app.bot.middlewares.db_middleware import DbSessionMiddleware
from app.bot.middlewares.error_middleware import ErrorLoggingMiddleware
from app.bot.middlewares.user_middleware import EnsureUserMiddleware
from app.config import settings


def create_bot() -> Bot:
    return Bot(
        token=settings.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    # Register middlewares (order matters: error → db → user)
    dp.message.middleware(ErrorLoggingMiddleware())
    dp.callback_query.middleware(ErrorLoggingMiddleware())

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.message.middleware(EnsureUserMiddleware())
    dp.callback_query.middleware(EnsureUserMiddleware())

    # Register routers (order matters for handler priority)
    dp.include_router(cancel.router)
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(consent.router)
    dp.include_router(menu.router)
    dp.include_router(help_handler.router)
    dp.include_router(settings_handler.router)
    dp.include_router(payment.router)
    dp.include_router(flirt.router)
    dp.include_router(first_message.router)
    dp.include_router(analyzer.router)
    dp.include_router(anti_ignor.router)
    dp.include_router(photo_pickup.router)
    dp.include_router(modifier.router)  # Must be last — handles generic postgen callbacks

    return dp
