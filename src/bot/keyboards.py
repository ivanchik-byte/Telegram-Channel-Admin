from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from src.core.i18n import i18n, TRANSLATIONS


def kb_variants(key: str) -> set:
    """All language variants of a reply-keyboard label."""
    return {TRANSLATIONS[lang].get(key, '') for lang in ('ru', 'en')} - {''}


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
