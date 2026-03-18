"""Payment / subscription handlers (stub implementation)."""

from __future__ import annotations

import datetime
import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.payment import payment_confirm_keyboard, payment_menu_keyboard
from app.bot.keyboards.scenarios import back_to_menu_keyboard
from app.services.access_service import AccessStatus, check_access
from app.services.payment_service import confirm_stub_payment, create_stub_payment

router = Router(name="payment")
logger = logging.getLogger(__name__)

ACCESS_LABELS = {
    "none": "⬜ Пробный период ещё не активирован",
    "trial": "⏳ Пробный период активен",
    "expired": "⌛ Пробный период истёк",
    "paid": "✅ Подписка активна",
}


@router.callback_query(F.data.in_({"menu:payment", "menu:subscription"}))
async def show_payment(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)

    # Build status text
    lines = [f"Статус: {label}"]

    if status == AccessStatus.TRIAL:
        from app.db.repositories import user_repo
        access = await user_repo.get_access(db_session, user_id)
        if access and access.trial_expires_at:
            now = datetime.datetime.now(datetime.UTC)
            remaining = access.trial_expires_at - now
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                lines.append(f"Осталось: {minutes} мин.")

    if status in (AccessStatus.EXPIRED, AccessStatus.NONE):
        lines.append("\nЧтобы продолжить — оформите подписку.")
        lines.append("Стоимость: 299 ₽ / месяц")

    text = "\n".join(lines)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=payment_menu_keyboard())


@router.callback_query(F.data == "pay:create")
async def create_payment(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    tx_id = await create_stub_payment(db_session, user_id)
    await db_session.commit()

    await callback.answer()
    await callback.message.edit_text(
        f"Заявка на оплату создана.\nID: {tx_id}\n\n"
        "В рабочей версии здесь будет ссылка для оплаты.\n"
        "Для тестирования нажмите кнопку подтверждения ниже.",
        reply_markup=payment_confirm_keyboard(str(tx_id)),
    )


@router.callback_query(F.data.startswith("pay:confirm:"))
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    tx_id_str = callback.data.split(":")[-1]
    try:
        tx_id = uuid.UUID(tx_id_str)
    except ValueError:
        await callback.answer("Неверный ID транзакции.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    result = await confirm_stub_payment(db_session, tx_id, user_id)
    await db_session.commit()

    if result.success:
        await callback.answer("Оплата подтверждена ✓")
        await callback.message.edit_text(
            "✅ Оплата прошла успешно! Доступ активирован на 30 дней.",
            reply_markup=back_to_menu_keyboard(),
        )

        # Notify referrer about the bonus
        if result.referrer_telegram_id is not None:
            try:
                await callback.bot.send_message(
                    chat_id=result.referrer_telegram_id,
                    text=(
                        f"🎉 По вашей реферальной ссылке кто-то оформил подписку!\n"
                        f"Вам начислено +{result.referral_bonus_days} дней бесплатного доступа."
                    ),
                )
            except Exception:
                logger.warning(
                    "Failed to send referral bonus notification to telegram_id=%s",
                    result.referrer_telegram_id,
                )
    else:
        await callback.answer("Транзакция не найдена или уже обработана.")
        await callback.message.edit_text(
            "Транзакция не найдена или уже была обработана ранее.",
            reply_markup=back_to_menu_keyboard(),
        )


@router.callback_query(F.data == "pay:check")
async def check_payment_status(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)
    await callback.answer(f"Статус: {label}", show_alert=True)
