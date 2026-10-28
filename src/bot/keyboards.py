from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from src.core.i18n import i18n, TRANSLATIONS


# Previously sent reply keyboards remain clickable after an upgrade.
LEGACY_REPLY_LABELS = {
    'kb_moderation': {'\U0001f4cb Модерация', '\U0001f4cb Moderation'},
    'kb_status': {'\U0001f4ca Статус', '\U0001f4ca Status'},
    'kb_parse_now': {'\U0001f504 Парсить сейчас', '\U0001f504 Parse now'},
    'kb_find_best': {'\u2b50 Найти лучший пост', '\u2b50 Find best post'},
    'kb_pause_8h': {'\u23f8 Пауза 8ч', '\u23f8 Pause 8h'},
    'kb_resume': {'\u25b6 Возобновить', '\u25b6 Resume'},
    'kb_clear_all': {'\U0001f5d1 Очистить все', '\U0001f5d1 Clear all'},
    'kb_clear_db': {'\U0001f5c4 Очистить БД', '\U0001f5c4 Clear DB'},
}


def kb_variants(key: str) -> set:
    """All language variants of a reply-keyboard label."""
    return ({TRANSLATIONS[lang].get(key, '') for lang in ('ru', 'en')} - {''}) | LEGACY_REPLY_LABELS.get(key, set())


def get_main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n.get('kb_moderation')),
                KeyboardButton(text=i18n.get('kb_status'))
            ],
            [
                KeyboardButton(text=i18n.get('kb_parse_now')),
                KeyboardButton(text=i18n.get('kb_find_best'))
            ],
            [
                KeyboardButton(text=i18n.get('kb_pause_8h')),
                KeyboardButton(text=i18n.get('kb_resume'))
            ],
            [
                KeyboardButton(text=i18n.get('kb_clear_all')),
                KeyboardButton(text=i18n.get('kb_clear_db'))
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder=i18n.get('kb_input_placeholder')
    )


def get_main_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('ib_moderation'), callback_data="menu_moderation"),
            InlineKeyboardButton(text=i18n.get('ib_refresh_status'), callback_data="menu_status")
        ],
        [
            InlineKeyboardButton(text=i18n.get('ib_parse_now'), callback_data="menu_parse"),
            InlineKeyboardButton(text=i18n.get('ib_find_best'), callback_data="menu_best")
        ],
        [
            InlineKeyboardButton(text=i18n.get('ib_pause_8h'), callback_data="menu_pause_8h"),
            InlineKeyboardButton(text=i18n.get('ib_resume'), callback_data="menu_resume")
        ],
        [
            InlineKeyboardButton(text=i18n.get('ib_clear_all'), callback_data="menu_clear_all"),
            InlineKeyboardButton(text=i18n.get('ib_clear_db'), callback_data="menu_clear_db")
        ],
        [
            InlineKeyboardButton(text=i18n.get('ib_languages'), callback_data="menu_languages"),
            InlineKeyboardButton(text=i18n.get('ib_prompt'), callback_data="menu_prompt")
        ]
    ])
