"""FSM states for onboarding flow."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    gender = State()
    style = State()
    identity = State()
