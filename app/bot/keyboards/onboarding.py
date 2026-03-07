"""Keyboards for the onboarding flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мужчина", callback_data="onb:gender:male")],
            [InlineKeyboardButton(text="Женщина", callback_data="onb:gender:female")],
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:gender:skip")],
        ],
    )


def situation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сайт знакомств", callback_data="onb:sit:dating_site")],
            [InlineKeyboardButton(text="Реальное общение", callback_data="onb:sit:real_life")],
            [InlineKeyboardButton(text="Переписка после знакомства", callback_data="onb:sit:after_meeting")],
            [InlineKeyboardButton(text="Другое", callback_data="onb:sit:other")],
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:sit:skip")],
        ],
    )


def role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Инициатор общения", callback_data="onb:role:initiator")],
            [InlineKeyboardButton(text="Продолжаю диалог", callback_data="onb:role:continuing")],
            [InlineKeyboardButton(text="Хочу перейти к встрече", callback_data="onb:role:meeting")],
            [InlineKeyboardButton(text="Другое", callback_data="onb:role:other")],
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:role:skip")],
        ],
    )


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:skip")],
        ],
    )
