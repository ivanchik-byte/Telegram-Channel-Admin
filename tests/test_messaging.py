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
