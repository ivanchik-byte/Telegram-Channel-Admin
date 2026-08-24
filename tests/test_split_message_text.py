from src.core.utils import split_message_text


class TestBasics:
    def test_empty_string(self):
        assert split_message_text("", 10) == []

    def test_short_text_single_chunk(self):
        assert split_message_text("hello", 10) == ["hello"]

    def test_exact_limit_single_chunk(self):
        text = "a" * 10
        assert split_message_text(text, 10) == [text]

    def test_one_over_limit_two_chunks(self):
        chunks = split_message_text("a" * 11, 10)
        assert len(chunks) == 2
        assert all(len(c) <= 10 for c in chunks)


class TestContentPreservation:
    def test_roundtrip_multiline(self):
        text = "\n".join(f"line {i} with some words" for i in range(200))
        chunks = split_message_text(text, 50)
        joined = "\n".join(chunks)
        # every original line must survive intact
        for line in text.split("\n"):
            assert any(line in c for c in chunks), f"line lost: {line!r}"
        # no chunk exceeds the limit
        assert all(len(c) <= 50 for c in chunks)

    def test_hard_split_overlong_line(self):
        chunks = split_message_text("x" * 25, 10)
        assert all(len(c) <= 10 for c in chunks)
        assert "".join(chunks) == "x" * 25

    def test_overlong_line_with_prefix(self):
        chunks = split_message_text("ab\n" + "y" * 15 + "\ncd", 10)
        assert "".join(c.replace("\n", "") for c in chunks) == "ab" + "y" * 15 + "cd"
        assert all(len(c) <= 10 for c in chunks)


class TestTelegramLimits:
    def test_default_limit_is_4096(self):
        import inspect
        sig = inspect.signature(split_message_text)
        assert sig.parameters["limit"].default == 4096

    def test_long_post_chunks_within_limit(self):
        text = ("Абзац текста про технологии и нейросети.\n" * 500)
        chunks = split_message_text(text)
        assert all(len(c) <= 4096 for c in chunks)
