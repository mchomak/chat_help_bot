"""FSM states for settings editing."""

from aiogram.fsm.state import State, StatesGroup


class SettingsEditStates(StatesGroup):
    editing_gender = State()
    editing_style = State()
    editing_identity = State()
