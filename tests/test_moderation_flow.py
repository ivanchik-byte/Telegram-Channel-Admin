from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.routers import moderation
from src.core.constants import TG_CAPTION_LIMIT, TG_MESSAGE_LIMIT
from src.core.utils import strip_html


@pytest.mark.parametrize('has_media', [True, False])
@pytest.mark.parametrize('status_key', ['msg_published', 'msg_rejected'])
async def test_completed_card_fits_telegram_limits_and_escapes_content(has_media, status_key):
    message = SimpleNamespace(
        photo=['photo'] if has_media else None, video=None, document=None,
        edit_caption=AsyncMock(), edit_text=AsyncMock(),
    )
    callback = SimpleNamespace(
        message=message,
        from_user=SimpleNamespace(username='<admin>', full_name='Admin'),
    )
    post = SimpleNamespace(id=42, rewritten_text='<b>draft</b> ' + '\U0001f600&' * 3000)
    await moderation.finish_mod_card(callback, post, status_key)

    edit = message.edit_caption if has_media else message.edit_text
    caption = edit.await_args.kwargs['caption' if has_media else 'text']
    limit = TG_CAPTION_LIMIT if has_media else TG_MESSAGE_LIMIT
    assert len(strip_html(caption).encode('utf-16-le')) // 2 <= limit
    assert '#42' in caption
    assert '&lt;admin&gt;' in caption
    assert caption.endswith('…')
    assert edit.await_args.kwargs['reply_markup'] is None


async def test_ai_edit_does_not_send_draft_if_post_was_processed_during_ai_call(monkeypatch):
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock()
    session_context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(moderation, 'async_session_maker', lambda: session_context)
    monkeypatch.setattr(
        moderation.PostRepository, 'get_post_by_id',
        AsyncMock(return_value=SimpleNamespace(status='moderating', rewritten_text='Old draft', text='Source')),
    )
    monkeypatch.setattr(moderation.PostRepository, 'atomic_edit_text', AsyncMock(return_value=None))
    monkeypatch.setattr(moderation, 'ai_custom_edit', AsyncMock(return_value=('New draft', None)))
    send_card = AsyncMock()
    monkeypatch.setattr(moderation, 'send_mod_card_to_chat', send_card)
    progress = SimpleNamespace(edit_text=AsyncMock())
    message = SimpleNamespace(text='Make it shorter', reply=AsyncMock(return_value=progress))
    state = SimpleNamespace(
        get_data=AsyncMock(return_value={'post_id': 42, 'mod_card_message_id': 7}), clear=AsyncMock(),
    )

    await moderation.receive_ai_instruction(message, state, SimpleNamespace())

    send_card.assert_not_awaited()
    progress.edit_text.assert_awaited_once()
    state.clear.assert_awaited_once()
