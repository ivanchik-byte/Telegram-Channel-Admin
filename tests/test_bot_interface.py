import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandObject

from src.bot.keyboards import get_main_reply_keyboard, kb_variants
from src.bot.routers import setup_admin
from src.core.i18n import I18n, TRANSLATIONS, i18n


@pytest.mark.parametrize('language', ['ru', 'en'])
def test_bot_interface_has_no_emoji(language):
    emoji = re.compile('[\U0001F000-\U0001FAFF\u2300-\u23ff\u25b6\u2600-\u27bf\u2b50\u2b55\ufe0f\u200d]')
    assert not {key: text for key, text in TRANSLATIONS[language].items() if emoji.search(text)}


@pytest.mark.parametrize('language', ['ru', 'en'])
@pytest.mark.parametrize('key', ['lang_ui_set', 'lang_post_set', 'prompt_status_default', 'prompt_reset_done'])
def test_language_names_are_formatted_separately_from_translation_selector(language, key):
    translator = I18n(language)
    text = translator.get(key, language_name='English')
    assert 'English' in text
    assert '{' not in text


@pytest.mark.parametrize('command_args', ['-5', '5-', '1-2-3', '--', 'invalid'])
async def test_invalid_intervals_do_not_change_settings(command_args, monkeypatch):
    session_factory = AsyncMock()
    monkeypatch.setattr(setup_admin, 'async_session_maker', session_factory)
    message = SimpleNamespace(reply=AsyncMock())

    await setup_admin.cmd_interval(message, CommandObject(command='interval', args=command_args))

    session_factory.assert_not_called()
    message.reply.assert_awaited_once_with(i18n.get('interval_invalid'))


def test_previous_reply_keyboard_labels_are_still_recognized():
    assert '\U0001f504 Парсить сейчас' in kb_variants('kb_parse_now')
    assert '\U0001f504 Parse now' in kb_variants('kb_parse_now')
    keyboard = get_main_reply_keyboard()
    for row in keyboard.keyboard:
        for button in row:
            assert any(button.text in kb_variants(key) for key in TRANSLATIONS['ru'] if key.startswith('kb_'))


async def test_start_exits_text_editing_instead_of_saving_command_as_draft(monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import MagicMock
    from aiogram import Bot, Dispatcher
    from aiogram.types import Chat, Message, Update, User
    from src.bot.handlers import router
    from src.bot.states import TextReplacement

    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock()
    session_context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(setup_admin, 'async_session_maker', lambda: session_context)
    monkeypatch.setattr(setup_admin.settings, 'ADMIN_IDS', [123])
    monkeypatch.setattr(i18n, 'lang', 'ru')
    monkeypatch.setattr(
        setup_admin.SettingsRepository, 'get_settings',
        AsyncMock(return_value=SimpleNamespace(ui_lang='ru')),
    )
    edit_post = AsyncMock()
    monkeypatch.setattr(setup_admin.PostRepository, 'atomic_edit_text', edit_post)
    bot = Bot('123456:test-token')
    sent = AsyncMock()
    monkeypatch.setattr(bot.session, 'make_request', sent)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    state = dispatcher.fsm.get_context(bot=bot, chat_id=123, user_id=123)
    await state.set_state(TextReplacement.waiting_for_text)
    await state.update_data(post_id=42)
    message = Message(
        message_id=1, date=datetime.now(timezone.utc),
        chat=Chat(id=123, type='private'),
        from_user=User(id=123, is_bot=False, first_name='Admin'), text='/start',
    )
    try:
        await dispatcher.feed_update(bot, Update(update_id=1, message=message))
        assert await state.get_state() is None
        edit_post.assert_not_awaited()
        assert sent.await_count == 2
    finally:
        await bot.session.close()
        await dispatcher.storage.close()
