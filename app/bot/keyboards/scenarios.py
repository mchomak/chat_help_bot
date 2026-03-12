"""Post-result and navigation inline keyboards for AI scenarios."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.styles import STYLE_OPTIONS


def post_generation_keyboard(scenario: str) -> InlineKeyboardMarkup:
    """Universal keyboard shown after any AI generation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Изменить стиль",
                    callback_data=f"postgen:chstyle:{scenario}",
                ),
                InlineKeyboardButton(
                    text="Еще варианты",
                    callback_data=f"postgen:more:{scenario}",
                ),
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data=f"back:{scenario}"),
                InlineKeyboardButton(text="Меню", callback_data="back:menu"),
            ],
        ],
    )


def post_generation_style_keyboard(scenario: str) -> InlineKeyboardMarkup:
    """Style picker shown when user clicks 'Изменить стиль' after generation."""
    buttons = []
    for key, label in STYLE_OPTIONS.items():
        buttons.append(
            [InlineKeyboardButton(
                text=label,
                callback_data=f"restyle:{scenario}:{key}",
            )]
        )
    buttons.append(
        [InlineKeyboardButton(text="Назад", callback_data=f"back:{scenario}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def input_method_keyboard(scenario: str) -> InlineKeyboardMarkup:
    """Keyboard for choosing input method (screenshot / text / both)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Скрин профиля",
                callback_data=f"input:{scenario}:screenshot",
            )],
            [InlineKeyboardButton(
                text="Описание текстом",
                callback_data=f"input:{scenario}:text",
            )],
            [InlineKeyboardButton(
                text="Скрин + описание",
                callback_data=f"input:{scenario}:both",
            )],
            [
                InlineKeyboardButton(text="Назад", callback_data=f"back:{scenario}"),
                InlineKeyboardButton(text="Меню", callback_data="back:menu"),
            ],
        ],
    )


def analyzer_input_method_keyboard() -> InlineKeyboardMarkup:
    """Input method keyboard for the dialog analyzer."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Скрин переписки",
                callback_data="input:analyzer:screenshot",
            )],
            [InlineKeyboardButton(
                text="Переписка текстом",
                callback_data="input:analyzer:text",
            )],
            [
                InlineKeyboardButton(text="Назад", callback_data="back:analyzer"),
                InlineKeyboardButton(text="Меню", callback_data="back:menu"),
            ],
        ],
    )


def anti_ignor_time_keyboard() -> InlineKeyboardMarkup:
    """Time selection for anti-ignor scenario."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 день", callback_data="aitime:1day"),
                InlineKeyboardButton(text="2-3 дня", callback_data="aitime:2-3days"),
            ],
            [
                InlineKeyboardButton(text="Неделя", callback_data="aitime:week"),
                InlineKeyboardButton(text="Другое", callback_data="aitime:other"),
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="back:anti_ignor"),
                InlineKeyboardButton(text="Меню", callback_data="back:menu"),
            ],
        ],
    )


def nav_keyboard(back_target: str = "menu") -> InlineKeyboardMarkup:
    """Simple navigation keyboard with Back and Menu buttons."""
    buttons = []
    if back_target != "menu":
        buttons.append(InlineKeyboardButton(text="Назад", callback_data=f"back:{back_target}"))
    buttons.append(InlineKeyboardButton(text="Меню", callback_data="back:menu"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Меню", callback_data="back:menu")],
        ],
    )


def error_with_retry_keyboard() -> InlineKeyboardMarkup:
    """Error keyboard with retry and menu buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать ещё раз", callback_data="retry:last")],
            [InlineKeyboardButton(text="Меню", callback_data="back:menu")],
        ],
    )


def suggest_first_message_keyboard() -> InlineKeyboardMarkup:
    """Keyboard suggesting to switch to first message generator."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Генератор первых сообщений",
                callback_data="menu:first_message",
            )],
            [InlineKeyboardButton(text="Меню", callback_data="back:menu")],
        ],
    )


# Legacy keyboards kept for backward compatibility with modifier handler
def reply_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return post_generation_keyboard("analyzer")


def first_msg_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return post_generation_keyboard("first_message")


def profile_result_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return post_generation_keyboard("profile_review")
