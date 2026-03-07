"""FSM states for AI scenarios."""

from aiogram.fsm.state import State, StatesGroup


class ReplyMessageStates(StatesGroup):
    waiting_input = State()


class FirstMessageStates(StatesGroup):
    waiting_input = State()


class ProfileReviewStates(StatesGroup):
    waiting_input = State()


class ConsentStates(StatesGroup):
    waiting_consent = State()
