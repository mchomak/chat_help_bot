"""Payment / subscription handlers — YooKassa flow."""

from __future__ import annotations

import datetime
import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app import tariffs_config
from app.bot.keyboards.payment import (
    pack_selection_keyboard,
    payment_error_keyboard,
    payment_menu_keyboard,
    payment_pending_keyboard,
    tariff_selection_keyboard,
)
from app.bot.keyboards.scenarios import back_to_menu_keyboard
from app.db.repositories import payment_repo, user_repo
from app.db.models.payment import PaymentStatus
from app.services.access_service import AccessStatus, check_access
from app.services.payment_service import create_and_initiate_payment, poll_and_process_payment

router = Router(name="payment")
logger = logging.getLogger(__name__)

ACCESS_LABELS = {
    "none": "⬜ Пробный период ещё не активирован",
    "trial": "⏳ Пробный период активен",
    "expired": "⌛ Пробный период истёк",
    "paid": "✅ Подписка активна",
}


# ── Subscription status screen ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"menu:payment", "menu:subscription"}))
async def show_payment(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)
    lines = [f"Статус: {label}"]

    if status == AccessStatus.TRIAL:
        access = await user_repo.get_access(db_session, user_id)
        if access and access.trial_expires_at:
            now = datetime.datetime.now(datetime.UTC)
            remaining = access.trial_expires_at - now
            if remaining.total_seconds() > 0:
                minutes = int(remaining.total_seconds() // 60)
                lines.append(f"Осталось времени: {minutes} мин.")

    if status == AccessStatus.PAID:
        access = await user_repo.get_access(db_session, user_id)
        if access:
            lines.append(f"Скриншотов осталось: {access.screenshots_balance}")
            if access.paid_until:
                lines.append(f"Подписка до: {access.paid_until.strftime('%d.%m.%Y')}")

    if status in (AccessStatus.EXPIRED, AccessStatus.NONE):
        lines.append("\nЧтобы продолжить — оформите подписку.")

    await callback.answer()
    await callback.message.edit_text("\n".join(lines), reply_markup=payment_menu_keyboard())


# ── Tariff selection ────────────────────────────────────────────────────────

@router.callback_query(F.data == "pay:select_tariff")
async def select_tariff(callback: types.CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "Выберите тариф подписки:\n\n"
        "В каждый тариф включены базовые скриншоты. "
        "Неиспользованные скриншоты сгорают по окончании периода.",
        reply_markup=tariff_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("pay:tariff:"))
async def create_tariff_payment(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    tariff_key = callback.data.split(":")[-1]
    try:
        plan = tariffs_config.get_tariff(tariff_key)
    except KeyError:
        await callback.answer("Неверный тариф.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    await callback.answer()
    await callback.message.edit_text("⏳ Создаём счёт на оплату...")

    result = await create_and_initiate_payment(
        db_session, user_id=user_id, purchase_type="tariff", purchase_key=tariff_key,
    )

    if result.payment_url:
        await callback.message.edit_text(
            f"Тариф: {plan.label}\n"
            f"Сумма: {int(plan.price)} ₽\n"
            f"Срок: {plan.days} дн. · Скриншоты: {plan.base_screenshots} шт.\n\n"
            "Нажмите кнопку для перехода к оплате. "
            "После оплаты вернитесь и нажмите «Проверить статус».",
            reply_markup=payment_pending_keyboard(result.payment_url, str(result.payment_id)),
        )
    else:
        await callback.message.edit_text(
            "⚠️ Не удалось создать счёт на оплату. Попробуйте позже.",
            reply_markup=payment_error_keyboard(),
        )


# ── Screenshot pack selection ───────────────────────────────────────────────

@router.callback_query(F.data == "pay:select_pack")
async def select_pack(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)

    if status not in (AccessStatus.TRIAL, AccessStatus.PAID):
        await callback.answer("Пакеты скриншотов доступны только при активной подписке.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "Выберите пакет скриншотов:\n\n"
        "Скриншоты добавятся к текущему балансу. "
        "Они действуют до конца текущего оплаченного периода.",
        reply_markup=pack_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("pay:pack:"))
async def create_pack_payment(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    pack_key = callback.data.split(":")[-1]
    try:
        pack = tariffs_config.get_pack(pack_key)
    except KeyError:
        await callback.answer("Неверный пакет.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    await callback.answer()
    await callback.message.edit_text("⏳ Создаём счёт на оплату...")

    result = await create_and_initiate_payment(
        db_session, user_id=user_id, purchase_type="pack", purchase_key=pack_key,
    )

    if result.payment_url:
        await callback.message.edit_text(
            f"Пакет: {pack.label}\n"
            f"Сумма: {int(pack.price)} ₽\n\n"
            "Нажмите кнопку для перехода к оплате. "
            "После оплаты нажмите «Проверить статус».",
            reply_markup=payment_pending_keyboard(result.payment_url, str(result.payment_id)),
        )
    else:
        await callback.message.edit_text(
            "⚠️ Не удалось создать счёт на оплату. Попробуйте позже.",
            reply_markup=payment_error_keyboard(),
        )


# ── Poll payment status (user-initiated) ────────────────────────────────────

@router.callback_query(F.data.startswith("pay:poll:"))
async def poll_payment(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    payment_id_str = callback.data.split(":")[-1]
    try:
        payment_id = uuid.UUID(payment_id_str)
    except ValueError:
        await callback.answer("Неверный ID платежа.")
        return

    await callback.answer("Проверяем статус...")

    new_status = await poll_and_process_payment(db_session, callback.bot, payment_id)
    await db_session.commit()

    if new_status == PaymentStatus.SUCCEEDED:
        await callback.message.edit_text(
            "✅ Оплата подтверждена! Доступ и скриншоты уже начислены.",
            reply_markup=back_to_menu_keyboard(),
        )
    elif new_status == PaymentStatus.CANCELED:
        await callback.message.edit_text(
            "❌ Платёж отменён. Вы можете создать новый.",
            reply_markup=payment_menu_keyboard(),
        )
    elif new_status == PaymentStatus.WAITING_FOR_PAYMENT:
        payment = await payment_repo.get_payment(db_session, payment_id)
        if payment and payment.payment_url:
            await callback.answer("Оплата ещё не поступила.", show_alert=True)
        else:
            await callback.answer("Ожидаем оплату...", show_alert=True)
    else:
        await callback.answer(f"Статус: {new_status}", show_alert=True)


# ── General status check ─────────────────────────────────────────────────────

@router.callback_query(F.data == "pay:check")
async def check_payment_status(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)
    await callback.answer(f"Статус: {label}", show_alert=True)
