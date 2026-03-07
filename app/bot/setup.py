"""Bot and dispatcher factory."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    cancel,
    consent,
    first_message,
    help as help_handler,
    menu,
    modifier,
    onboarding,
    payment,
    profile_review,
    reply_message,
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

    # Register routers
    dp.include_router(cancel.router)
    dp.include_router(start.router)
    dp.include_router(onboarding.router)
    dp.include_router(consent.router)
    dp.include_router(menu.router)
    dp.include_router(help_handler.router)
    dp.include_router(settings_handler.router)
    dp.include_router(payment.router)
    dp.include_router(reply_message.router)
    dp.include_router(first_message.router)
    dp.include_router(profile_review.router)
    dp.include_router(modifier.router)

    return dp
