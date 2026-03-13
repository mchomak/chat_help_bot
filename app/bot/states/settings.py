"""FSM states for settings editing."""

from aiogram.fsm.state import State, StatesGroup


class SettingsEditStates(StatesGroup):
    editing_gender = State()
    editing_age = State()
    editing_city = State()
    editing_goals = State()
    editing_interests = State()
    editing_situation = State()
    editing_role = State()
    editing_identity = State()
