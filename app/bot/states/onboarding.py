"""FSM states for onboarding flow."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    gender = State()
    age = State()
    city = State()
    goals = State()
    interests = State()
    situation = State()
    role = State()
    identity = State()
