"""Messaging-layer contract tests.

These require the full runtime deps (aiogram). They run inside docker/CI;
locally they are skipped gracefully.
"""
import pytest

aiogram = pytest.importorskip("aiogram", reason="runtime deps not installed")

from src.bot.messaging import (  # noqa: E402
    build_mod_card_keyboard,
    send_long_message,
    TG_HTML_SPLIT_LIMIT,
)
from src.core.constants import TG_MESSAGE_LIMIT  # noqa: E402


class TestModCardKeyboard:
    def test_contains_all_actions(self):
        kb = build_mod_card_keyboard(42)
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert callbacks == [
            "publish_42", "reject_42",
            "edit_42", "change_media_42",
            "ai_edit_42",
        ]

    def test_post_id_is_scoped(self):
        kb = build_mod_card_keyboard(7)
        flat = str(kb.model_dump())
        assert "publish_7" in flat and "publish_42" not in flat


class TestSplitLimit:
    def test_split_margin_below_telegram_limit(self):
        """Formatted chunks must stay under the API limit: raw split limit
        leaves headroom for tags added by format_telegram_html."""
        assert TG_HTML_SPLIT_LIMIT < TG_MESSAGE_LIMIT


class TestSendLongMessage:
    @pytest.fixture()
    def fake_bot(self, monkeypatch):
        sent = []

        class FakeMessage:
            def __init__(self, text):
                self.text = text

        class FakeBot:
            async def send_message(self, chat_id, text, **kwargs):
                sent.append({"chat_id": chat_id, "text": text, **kwargs})
                return FakeMessage(text)

        return FakeBot(), sent

    async def test_raw_html_split_across_chunks_stays_valid(self, fake_bot):
        from src.core.utils import format_telegram_html
        bot, sent = fake_bot
        raw = ("Заголовок\n\n" + "текст " * 800 +
               '\n<a href="https://example.com/x">анкор</a>\n' + "хвост " * 300)

        await send_long_message(bot, 1, raw)

        assert len(sent) >= 2
        import re
        for msg in sent:
            assert len(msg["text"]) <= TG_MESSAGE_LIMIT
            # every chunk must be self-balanced HTML (tags may carry attributes)
            depth = 0
            for m in re.finditer(r"<(/?)(b|i|u|s|code|pre|blockquote|a|tg-spoiler)(?:\s[^>]*)?>", msg["text"]):
                depth += -1 if m.group(1) else 1
                assert depth >= 0, f"orphan closing tag in chunk: {msg['text'][:80]}"
            assert depth == 0, f"unbalanced HTML in chunk: {msg['text'][-80:]}"

        # content preserved across chunks
        joined = "".join(strip_tags(m["text"]) for m in sent)
        assert "анкор" in joined and "хвост" in joined


def strip_tags(text):
    import re
    from html import unescape
    return unescape(re.sub(r"<[^>]+>", "", text))


@pytest.mark.parametrize('media_type', ['photo', 'video', 'document'])
async def test_long_caption_keeps_buttons_on_text_and_preserves_media_options(media_type):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.bot.messaging import send_media_with_caption

    media_message = SimpleNamespace(delete=AsyncMock())
    bot = SimpleNamespace(
        send_photo=AsyncMock(return_value=media_message),
        send_video=AsyncMock(return_value=media_message),
        send_document=AsyncMock(return_value=media_message),
        send_message=AsyncMock(),
    )
    keyboard = build_mod_card_keyboard(42)
    await send_media_with_caption(
        bot, 1, media_type, 'file-id', 'long draft ' * 500,
        reply_markup=keyboard, disable_notification=True,
    )

    media_sender = getattr(bot, f'send_{media_type}')
    assert media_sender.await_args.kwargs['disable_notification'] is True
    assert 'reply_markup' not in media_sender.await_args.kwargs
    assert bot.send_message.await_args_list[-1].kwargs['reply_markup'] is keyboard
    assert all(call.kwargs['reply_markup'] is None for call in bot.send_message.await_args_list[:-1])


async def test_media_send_propagates_text_failure_and_removes_orphan_media():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from src.bot.messaging import send_media_with_caption

    media_message = SimpleNamespace(delete=AsyncMock())
    bot = SimpleNamespace(
        send_photo=AsyncMock(return_value=media_message),
        send_message=AsyncMock(side_effect=TimeoutError('delivery failed')),
    )
    with pytest.raises(TimeoutError, match='delivery failed'):
        await send_media_with_caption(bot, 1, 'photo', 'file-id', 'draft ' * 300)
    media_message.delete.assert_awaited_once()
    bot.send_message.assert_awaited_once()


async def test_html_parse_error_falls_back_without_inheriting_parse_mode():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    error = TelegramBadRequest(
        method=SendMessage(chat_id=1, text='draft'),
        message="Bad Request: can't parse entities",
    )
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[error, 'sent']))
    assert await send_long_message(bot, 1, '<b>draft</b>') == 'sent'
    assert bot.send_message.await_args.kwargs['text'] == 'draft'
    assert bot.send_message.await_args.kwargs['parse_mode'] is None


async def test_non_formatting_telegram_errors_are_not_retried_as_plain_text():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import SendMessage

    error = TelegramBadRequest(
        method=SendMessage(chat_id=1, text='draft'), message='Bad Request: chat not found',
    )
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=error))
    with pytest.raises(TelegramBadRequest, match='chat not found'):
        await send_long_message(bot, 1, 'draft')
    bot.send_message.assert_awaited_once()


async def test_long_message_failure_removes_already_sent_chunks():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    first_chunk = SimpleNamespace(delete=AsyncMock())
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=[first_chunk, TimeoutError('connection lost')]))
    with pytest.raises(TimeoutError, match='connection lost'):
        await send_long_message(bot, 1, 'draft ' * 1000)
    first_chunk.delete.assert_awaited_once()
