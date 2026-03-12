"""Keyboards for the onboarding flow."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def gender_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мужчина", callback_data="onb:gender:male")],
            [InlineKeyboardButton(text="Женщина", callback_data="onb:gender:female")],
        ],
    )


def situation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сайт знакомств", callback_data="onb:situation:dating_app")],
            [InlineKeyboardButton(text="Реальное общение", callback_data="onb:situation:real_life")],
            [InlineKeyboardButton(text="Другое", callback_data="onb:situation:other")],
        ],
    )


def role_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Инициатор", callback_data="onb:role:initiator")],
            [InlineKeyboardButton(text="Продолжаю диалог", callback_data="onb:role:continuing")],
            [InlineKeyboardButton(text="Хочу перейти к встрече", callback_data="onb:role:meeting")],
            [InlineKeyboardButton(text="Другое", callback_data="onb:role:other")],
        ],
    )


def skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="onb:skip")],
        ],
    )
