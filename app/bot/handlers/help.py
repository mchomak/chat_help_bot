"""Help handler."""

from __future__ import annotations

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.scenarios import back_to_menu_keyboard

router = Router(name="help")

HELP_TEXT = (
    "Что умеет бот:\n\n"
    "✉️ *Первое сообщение* — отправьте скриншот профиля или опишите человека "
    "текстом, и бот предложит несколько вариантов для начала разговора.\n\n"
    "💬 *Флирт* — пришлите скриншот переписки или фото, "
    "и бот сгенерирует флиртующие варианты ответа.\n\n"
    "🔍 *Анализатор диалога* — отправьте переписку, и бот разберёт динамику "
    "разговора и предложит подходящие ответы.\n\n"
    "🔄 *Анти-игнор* — если собеседник перестал отвечать, бот поможет "
    "мягко возобновить диалог без ощущения навязчивости.\n\n"
    "📸 *Подкаты по фото* — отправьте фото, и бот придумает остроумные "
    "комментарии к нему.\n\n"
    "💳 *Подписка* — управление доступом и оплата.\n\n"
    "⏳ Пробный период — 2 часа бесплатно, активируется при первом запросе.\n\n"
    "Ниже ссылки на тех. поддержку.\n\n"
    "Все варианты носят рекомендательный характер и не гарантируют результат."
)


def help_keyboard() -> InlineKeyboardMarkup:
    base_keyboard = back_to_menu_keyboard()

    support_buttons = [
        [
            InlineKeyboardButton(
                text="Канал ТП",
                url="https://t.me/chat_help_24",
            ),
            InlineKeyboardButton(
                text="Чат ТП",
                url="https://t.me/heelp24",
            ),
        ]
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[*base_keyboard.inline_keyboard, *support_buttons]
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=help_keyboard())


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: types.CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(HELP_TEXT, reply_markup=help_keyboard())