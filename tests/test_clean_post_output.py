from src.core.utils import clean_post_output


class TestWrappers:
    def test_post_wrapper_stripped(self):
        assert clean_post_output("<post>\nтекст\n</post>") == "текст"

    def test_article_wrapper_stripped(self):
        assert clean_post_output("<article>контент</article>") == "контент"

    def test_output_wrapper_case_insensitive(self):
        assert clean_post_output("<OUTPUT>data</OUTPUT>") == "data"

    def test_telegram_tags_survive(self):
        src = "<b>Заголовок</b>\n\nтело <code>код</code>"
        assert clean_post_output(src) == src


class TestPreambles:
    def test_russian_preamble_stripped(self):
        result = clean_post_output("Вот готовый пост:\n\n<b>текст</b>")
        assert result == "<b>текст</b>"

    def test_english_preamble_stripped(self):
        result = clean_post_output("Here is the rewritten post:\ntext")
        assert result == "text"


class TestArtifacts:
    def test_tokenizer_artifact_replaced(self):
        result = clean_post_output("инструменты như PyTorch")
        assert "như" not in result
        assert "таких как" in result

    def test_empty_and_none_like(self):
        assert clean_post_output("") == ""


class TestRealisticAiOutput:
    def test_full_pipeline_example(self):
        raw = "<post>\nВот пост:\n\n<b>Ruff v0.5</b>\n\nРелиз как всегда. <code>pip install -U ruff</code>\n\n</post>"
        result = clean_post_output(raw)
        assert result.startswith("<b>Ruff")
        assert "<post>" not in result and "Вот" not in result
