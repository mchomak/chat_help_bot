"""Payment / subscription handlers (stub implementation)."""

from __future__ import annotations

import datetime
import logging
import uuid

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.enums import ParseMode
from app.bot.keyboards.payment import (
    pack_selection_keyboard,
    payment_confirm_keyboard,
    payment_menu_keyboard,
    tariff_selection_keyboard,
)
from app.bot.keyboards.scenarios import back_to_menu_keyboard
from app.config import settings as app_settings
from app.db.repositories import user_repo
from app.services.access_service import AccessStatus, check_access
from app.services.payment_service import (
    confirm_pack_payment,
    confirm_tariff_payment,
    create_stub_payment,
)

router = Router(name="payment")
logger = logging.getLogger(__name__)

ACCESS_LABELS = {
    "none": "⬜ Пробный период ещё не активирован",
    "trial": "⏳ Пробный период активен",
    "expired": "⌛ Пробный период истёк",
    "paid": "✅ Подписка активна",
}

TARIFF_LABELS = {
    "week": "1 неделя",
    "month": "1 месяц",
    "quarter": "3 месяца",
}

PACK_LABELS = {
    "s": lambda: f"{app_settings.tariffs.pack_s_screenshots} скринов",
    "m": lambda: f"{app_settings.tariffs.pack_m_screenshots} скринов",
    "l": lambda: f"{app_settings.tariffs.pack_l_screenshots} скринов",
}


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
                paid_until_str = access.paid_until.strftime("%d.%m.%Y")
                lines.append(f"Подписка до: {paid_until_str}")

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
    tariff_key = callback.data.split(":")[-1]  # week / month / quarter
    try:
        price, days, screenshots = app_settings.tariffs.get_tariff(tariff_key)
    except KeyError:
        await callback.answer("Неверный тариф.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    label = TARIFF_LABELS.get(tariff_key, tariff_key)
    tx_id = await create_stub_payment(
        db_session, user_id, amount=price,
        comment=f"Tariff: {tariff_key}",
    )
    await db_session.commit()

    await callback.answer()
    await callback.message.edit_text(
        f"Тариф: {label}\n"
        f"Сумма: {int(price)} ₽\n"
        f"Срок: {days} дн.\n"
        f"Скриншоты: {screenshots} шт.\n\n"
        "В рабочей версии здесь будет ссылка для оплаты.\n"
        "Для тестирования нажмите кнопку ниже.",
        reply_markup=payment_confirm_keyboard(str(tx_id), "tariff", tariff_key),
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
    pack_key = callback.data.split(":")[-1]  # s / m / l
    try:
        price, screenshots = app_settings.tariffs.get_pack(pack_key)
    except KeyError:
        await callback.answer("Неверный пакет.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    tx_id = await create_stub_payment(
        db_session, user_id, amount=price,
        comment=f"Pack: {pack_key}",
    )
    await db_session.commit()

    await callback.answer()
    await callback.message.edit_text(
        f"Пакет скриншотов: {screenshots} шт.\n"
        f"Сумма: {int(price)} ₽\n\n"
        "Для тестирования нажмите кнопку ниже.",
        reply_markup=payment_confirm_keyboard(str(tx_id), "pack", pack_key),
    )


# ── Confirm (stub) ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:confirm:"))
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession) -> None:
    # callback data: pay:confirm:{purchase_type}:{key}:{tx_id}
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Неверный формат данных.")
        return

    purchase_type = parts[2]   # tariff / pack
    purchase_key = parts[3]    # week/month/quarter or s/m/l
    tx_id_str = parts[4]

    try:
        tx_id = uuid.UUID(tx_id_str)
    except ValueError:
        await callback.answer("Неверный ID транзакции.")
        return

    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])

    if purchase_type == "tariff":
        result = await confirm_tariff_payment(db_session, tx_id, user_id, purchase_key)
        if result.success:
            _, days, screenshots = app_settings.tariffs.get_tariff(purchase_key)
            success_text = (
                f"✅ Оплата прошла успешно!\n"
                f"Доступ активирован на {days} дн., скриншоты: {screenshots} шт."
            )
        else:
            success_text = ""

    elif purchase_type == "pack":
        result = await confirm_pack_payment(db_session, tx_id, user_id, purchase_key)
        if result.success:
            _price, screenshots = app_settings.tariffs.get_pack(purchase_key)
            success_text = f"✅ Пакет добавлен! +{screenshots} скриншотов к балансу."
        else:
            success_text = ""
    else:
        await callback.answer("Неизвестный тип покупки.")
        return

    await db_session.commit()

    if result.success:
        await callback.answer("Оплата подтверждена ✓")
        await callback.message.edit_text(success_text, reply_markup=back_to_menu_keyboard())

        # Send referral bonus notification if applicable
        if result.referrer_telegram_id is not None:
            try:
                await callback.bot.send_message(
                    chat_id=result.referrer_telegram_id,
                    text=(
                        "🎉 По вашей реферальной ссылке кто-то оформил подписку!\n\n"
                        f"Вам начислено:\n"
                        f"• +{result.referral_bonus_days} дней доступа\n"
                        f"• +{result.referral_bonus_screenshots} скриншотов"
                    ),
                )
            except Exception:
                logger.warning(
                    "Failed to send referral bonus notification to telegram_id=%s",
                    result.referrer_telegram_id,
                )
    else:
        await callback.answer("Транзакция не найдена или уже была обработана.")
        await callback.message.edit_text(
            "Транзакция не найдена или уже была обработана ранее.",
            reply_markup=back_to_menu_keyboard(),
        )


@router.callback_query(F.data == "pay:check")
async def check_payment_status(
    callback: types.CallbackQuery, state: FSMContext, db_session: AsyncSession,
) -> None:
    data = await state.get_data()
    user_id = uuid.UUID(data["user_id"])
    status = await check_access(db_session, user_id)
    label = ACCESS_LABELS.get(status, status)
    await callback.answer(f"Статус: {label}", show_alert=True)
