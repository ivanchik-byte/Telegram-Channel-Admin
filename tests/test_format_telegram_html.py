import pytest

from src.core.utils import format_telegram_html


class TestEscaping:
    def test_plain_text_unchanged(self):
        assert format_telegram_html("просто текст") == "просто текст"

    def test_html_special_chars_escaped(self):
        result = format_telegram_html("a < b & c > d")
        assert "&lt;" in result and "&amp;" in result and "&gt;" in result

    def test_script_tag_neutralized(self):
        result = format_telegram_html("<script>alert(1)</script>")
        assert "<script>" not in result
        # it must appear escaped, not executed
        assert "&lt;script&gt;" in result


class TestAllowedTags:
    def test_bold_preserved(self):
        assert format_telegram_html("<b>жирный</b>") == "<b>жирный</b>"

    def test_code_and_spoiler_preserved(self):
        assert format_telegram_html("<code>x</code>") == "<code>x</code>"
        assert format_telegram_html("<tg-spoiler>s</tg-spoiler>") == "<tg-spoiler>s</tg-spoiler>"

    def test_link_with_href_preserved_and_escaped(self):
        result = format_telegram_html('<a href="https://x.com/?a=1&b=2">link</a>')
        assert '<a href="https://x.com/?a=1&amp;b=2">link</a>' == result

    def test_link_without_href_not_live(self):
        result = format_telegram_html('<a onclick="evil()">x</a>')
        # no LIVE anchor tag may survive without href; at most escaped text
        assert "<a" not in result
        assert "<script" not in result.lower()

    def test_disallowed_tag_escaped(self):
        result = format_telegram_html("<blink>wow</blink>")
        assert "&lt;blink&gt;" in result


class TestBalancing:
    def test_unclosed_tags_closed_at_end(self):
        result = format_telegram_html("<b>bold <i>both")
        assert result.count("<b>") == 1 and result.count("</b>") == 1
        assert result.count("<i>") == 1 and result.count("</i>") == 1

    def test_dangling_close_discarded_mid_text(self):
        result = format_telegram_html("text <i>orphan</i></b> tail")
        # the stray </b> must not survive as a real tag
        assert result.count("</b>") == 0 or result.count("<b>") >= result.count("</b>")

    def test_mismatched_nesting_fixed(self):
        result = format_telegram_html("<b>a<i>b</b>c</i>d")
        # output must be balanced whatever the input
        stack_depth = 0
        import re
        for m in re.finditer(r"<(/?)([a-z]+)[^>]*>", result):
            if m.group(2) not in ("b", "i"):
                continue
            stack_depth += -1 if m.group(1) else 1
            assert stack_depth >= 0, "closing tag without opener"
        assert stack_depth == 0, "unbalanced tags remain"


class TestMarkdownConversion:
    def test_markdown_bold_converted(self):
        assert format_telegram_html("**hi**") == "<b>hi</b>"

    def test_markdown_code_converted(self):
        assert format_telegram_html("`pip install`") == "<code>pip install</code>"

    def test_markdown_spoiler_converted(self):
        assert format_telegram_html("||secret||") == "<tg-spoiler>secret</tg-spoiler>"


class TestHeadlineFix:
    def test_dangling_close_in_first_line_reopened(self):
        # intentional feature: AI sometimes emits "</b>" headline without opener
        result = format_telegram_html("Заголовок</b>\n\nтело")
        first_line = result.split("\n")[0]
        assert first_line.startswith("<b>") and first_line.endswith("</b>")

    def test_empty_string(self):
        assert format_telegram_html("") == ""

    def test_none_like_empty(self):
        assert format_telegram_html("") != None  # noqa: E711 — returns str always
