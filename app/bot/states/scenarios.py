"""FSM states for AI scenarios."""

from aiogram.fsm.state import State, StatesGroup


class ConsentStates(StatesGroup):
    waiting_consent = State()


class FirstMessageStates(StatesGroup):
    choosing_style = State()
    choosing_input_method = State()
    waiting_input = State()


class AnalyzerStates(StatesGroup):
    choosing_input_method = State()
    choosing_style = State()
    waiting_input = State()


class AntiIgnorStates(StatesGroup):
    choosing_style = State()
    choosing_time = State()
    waiting_last_message = State()


class PhotoPickupStates(StatesGroup):
    choosing_style = State()
    waiting_photo = State()


class FlirtStates(StatesGroup):
    waiting_input = State()


class PostGenStates(StatesGroup):
    """State for post-generation style change."""
    choosing_new_style = State()


# Keep for backward compatibility
class ReplyMessageStates(StatesGroup):
    waiting_input = State()


class ProfileReviewStates(StatesGroup):
    waiting_input = State()


class PaymentStates(StatesGroup):
    waiting_email = State()
