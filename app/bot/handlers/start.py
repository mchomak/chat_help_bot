"""Handler for /start command — consent gate then onboarding or menu."""

from __future__ import annotations

import logging

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import send_menu, start_onboarding
from app.bot.keyboards.consent import consent_keyboard
from app.bot.keyboards.menu import PERSISTENT_MENU
from app.bot.states.scenarios import ConsentStates
from app.db.repositories import user_repo
from app.services.consent_service import has_consent

router = Router(name="start")
logger = logging.getLogger(__name__)

CONSENT_TEXT = (
    "👋 Привет! Я помогаю писать первые сообщения, отвечать в переписке "
    "и чувствовать себя увереннее в знакомствах.\n\n"
    "Перед началом, пожалуйста, ознакомьтесь с условиями и подтвердите своё согласие:\n\n"
    "• Вы отправляете текст и/или скриншоты для анализа\n"
    "• Данные используются для формирования AI-ответов\n"
    "• Сервис не гарантирует результат общения\n\n"
    "Нажимая «Принимаю», вы соглашаетесь с Пользовательским соглашением "
    "и Политикой конфиденциальности."
)


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, db_session: AsyncSession) -> None:
    user, created = await user_repo.get_or_create_user(
        db_session,
        telegram_id=message.from_user.id,
        defaults={
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "language_code": message.from_user.language_code,
        },
    )
    if not created:
        await user_repo.update_user_fields(
            db_session,
            user,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

    # Parse referral parameter from deep link: /start ref_<telegram_id>
    start_param = ""
    if message.text:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) == 2:
            start_param = parts[1]

    if created and start_param.startswith("ref_"):
        ref_telegram_id_str = start_param[4:]
        if ref_telegram_id_str.isdigit():
            ref_telegram_id = int(ref_telegram_id_str)
            # Don't let users refer themselves
            if ref_telegram_id != message.from_user.id:
                referrer = await user_repo.get_user_by_telegram_id(db_session, ref_telegram_id)
                if referrer is not None and user.referred_by_telegram_id is None:
                    user.referred_by_telegram_id = ref_telegram_id
                    logger.info(
                        "User %s referred by telegram_id=%s",
                        user.id, ref_telegram_id,
                    )

    await db_session.commit()

    await state.clear()
    await state.update_data(user_id=str(user.id))

    # Check consent first — without it, no access
    if await has_consent(db_session, user.id):
        # Already consented — check if onboarding done
        settings = await user_repo.get_user_settings(db_session, user.id)
        if settings and settings.onboarding_completed:
            await message.answer("С возвращением! 👋", reply_markup=PERSISTENT_MENU)
            await send_menu(message)
            return

        # Consent given but onboarding not finished — start onboarding
        await start_onboarding(message, state)
        return

    # No consent yet — ask for it
    await message.answer(CONSENT_TEXT, reply_markup=consent_keyboard())
    await state.set_state(ConsentStates.waiting_consent)
