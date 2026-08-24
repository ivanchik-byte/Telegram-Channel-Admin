from aiogram.fsm.state import State, StatesGroup


class MediaReplacement(StatesGroup):
    waiting_for_media = State()


class TextReplacement(StatesGroup):
    waiting_for_text = State()


class AIEditState(StatesGroup):
    waiting_for_instruction = State()


class PromptState(StatesGroup):
    waiting_for_prompt = State()
