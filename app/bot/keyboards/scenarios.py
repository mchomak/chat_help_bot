"""Post-result inline keyboards for AI scenarios."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def reply_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Еще варианты", callback_data=f"mod:reply_message:more:{request_id}"),
                InlineKeyboardButton(text="Мягче", callback_data=f"mod:reply_message:softer:{request_id}"),
            ],
            [
                InlineKeyboardButton(text="Увереннее", callback_data=f"mod:reply_message:confident:{request_id}"),
                InlineKeyboardButton(text="Короче", callback_data=f"mod:reply_message:shorter:{request_id}"),
            ],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def first_msg_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Еще варианты", callback_data=f"mod:first_message:more:{request_id}"),
                InlineKeyboardButton(text="Больше юмора", callback_data=f"mod:first_message:humor:{request_id}"),
            ],
            [
                InlineKeyboardButton(text="Увереннее", callback_data=f"mod:first_message:confident:{request_id}"),
                InlineKeyboardButton(text="Нейтрально", callback_data=f"mod:first_message:neutral:{request_id}"),
            ],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def profile_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Коротко", callback_data=f"mod:profile_review:short:{request_id}"),
                InlineKeyboardButton(text="Подробнее", callback_data=f"mod:profile_review:detailed:{request_id}"),
            ],
            [
                InlineKeyboardButton(text="Еще рекомендации", callback_data=f"mod:profile_review:more_recs:{request_id}"),
            ],
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="В меню", callback_data="back:menu")],
        ],
    )
