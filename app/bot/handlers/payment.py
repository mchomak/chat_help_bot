"""Payment / subscription handlers — YooKassa flow."""

from __future__ import annotations

import datetime
import logging
import uuid

from aiogram import F, Router, types
from aiogram.enums import ParseMode
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
from app.bot.states.scenarios import PaymentStates
from app.db.repositories import payment_repo, user_repo
from app.db.models.payment import PaymentStatus
from app.services.access_service import AccessStatus, check_access
from app.services.payment_service import create_and_initiate_payment, poll_and_process_payment
from aiogram.enums import ParseMode
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

    text = (
        "<b>Выберите тариф подписки:</b>\n\n"
        "Подписка даёт <b>полный доступ</b> ко всем функциям бота на выбранный срок.\n\n"
        "<b>Что входит в подписку:</b>\n\n"
        "• Полный доступ ко всем функциям\n\n"
        "• <b>Неограниченное количество текстовых запросов</b>\n\n"
        "• Базовый лимит скриншотов для анализа переписок и фото\n\n"
        "• Возможность докупить дополнительные скриншоты\n\n"
        "Оставшееся количество скриншотов можно посмотреть в разделе <b>«Подписка»</b>.\n\n"
        "Неиспользованные скриншоты <b>сгорают</b> после окончания периода."
    )

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=tariff_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("pay:tariff:"))
async def create_tariff_payment(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    tariff_key = callback.data.split(":")[-1]
    try:
        tariffs_config.get_tariff(tariff_key)
    except KeyError:
        await callback.answer("Неверный тариф.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await callback.answer()

    user = await user_repo.get_user_by_id(db_session, user_id)
    if user and user.email:
        await callback.message.edit_text("⏳ Создаём счёт на оплату...")
        await _do_create_payment(
            callback.message, db_session, user_id, "tariff", tariff_key, user.email,
        )
    else:
        await state.update_data(
            pending_purchase_type="tariff",
            pending_purchase_key=tariff_key,
        )
        await state.set_state(PaymentStates.waiting_email)
        await callback.message.edit_text(
            "📧 Для получения чека введите ваш e-mail:\n\n"
            "(Он нужен только для отправки фискального чека от YooKassa. "
            "Введите один раз — в следующий раз спрашивать не будем.)",
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
        tariffs_config.get_pack(pack_key)
    except KeyError:
        await callback.answer("Неверный пакет.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    await callback.answer()

    user = await user_repo.get_user_by_id(db_session, user_id)
    if user and user.email:
        await callback.message.edit_text("⏳ Создаём счёт на оплату...")
        await _do_create_payment(
            callback.message, db_session, user_id, "pack", pack_key, user.email,
        )
    else:
        await state.update_data(
            pending_purchase_type="pack",
            pending_purchase_key=pack_key,
        )
        await state.set_state(PaymentStates.waiting_email)
        await callback.message.edit_text(
            "📧 Для получения чека введите ваш e-mail:\n\n"
            "(Он нужен только для отправки фискального чека от YooKassa. "
            "Введите один раз — в следующий раз спрашивать не будем.)",
        )


# ── Email collection for receipt ────────────────────────────────────────────

@router.message(PaymentStates.waiting_email)
async def receive_email_for_payment(
    message: types.Message, state: FSMContext, db_session: AsyncSession,
) -> None:
    email = (message.text or "").strip().lower()
    if not _is_valid_email(email):
        await message.answer(
            "❌ Некорректный e-mail. Пожалуйста, введите действующий адрес (например, user@example.com)."
        )
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    purchase_type = data.get("pending_purchase_type")
    purchase_key = data.get("pending_purchase_key")

    # Save email to DB for future payments
    await user_repo.update_user_email(db_session, user_id, email)
    await db_session.commit()

    await state.set_state(None)

    if not purchase_type or not purchase_key:
        await message.answer("⚠️ Что-то пошло не так. Пожалуйста, начните оформление заново.")
        return

    status_msg = await message.answer("⏳ Создаём счёт на оплату...")
    await _do_create_payment(status_msg, db_session, user_id, purchase_type, purchase_key, email)


# ── Shared payment creation helper ──────────────────────────────────────────

async def _do_create_payment(
    message: types.Message,
    db_session: AsyncSession,
    user_id: uuid.UUID,
    purchase_type: str,
    purchase_key: str,
    customer_email: str,
) -> None:
    result = await create_and_initiate_payment(
        db_session,
        user_id=user_id,
        purchase_type=purchase_type,
        purchase_key=purchase_key,
        customer_email=customer_email,
    )

    if result.payment_url:
        if purchase_type == "tariff":
            plan = tariffs_config.get_tariff(purchase_key)
            text = (
                f"Тариф: {plan.label}\n"
                f"Сумма: {int(plan.price)} ₽\n"
                f"Срок: {plan.days} дн. · Скриншоты: {plan.base_screenshots} шт.\n\n"
                "Нажмите кнопку для перехода к оплате. "
                "После оплаты вернитесь и нажмите «Проверить статус»."
            )
        else:
            pack = tariffs_config.get_pack(purchase_key)
            text = (
                f"Пакет: {pack.label}\n"
                f"Сумма: {int(pack.price)} ₽\n\n"
                "Нажмите кнопку для перехода к оплате. "
                "После оплаты нажмите «Проверить статус»."
            )
        await message.edit_text(
            text,
            reply_markup=payment_pending_keyboard(result.payment_url, str(result.payment_id)),
        )
    else:
        await message.edit_text(
            "⚠️ Не удалось создать счёт на оплату. Попробуйте позже.",
            reply_markup=payment_error_keyboard(),
        )


def _is_valid_email(s: str) -> bool:
    """Basic email validation — no external dependency required."""
    if "@" not in s:
        return False
    local, _, domain = s.partition("@")
    return bool(local) and "." in domain and 5 <= len(s) <= 254


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
