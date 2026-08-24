import pytest

from src.core.adfilter import contains_ad
from src.core.config import settings


@pytest.fixture(autouse=True)
def ad_keywords(monkeypatch):
    monkeypatch.setattr(type(settings), "parsed_ad_keywords",
                        property(lambda self: ["реклама", "промокод", "erid"]))


class TestContainsAd:
    def test_clean_text_passes(self):
        assert contains_ad("Ruff v0.5 — быстрый линтер на Rust") is False

    def test_exact_keyword_hits(self):
        assert contains_ad("Это реклама") is True
        assert contains_ad("промокод2024") is True

    def test_russian_morphology_substring(self):
        # substring match intentionally catches word forms
        assert contains_ad("без рекламы не обходится") is True
        assert contains_ad("рекламодатели ликуют") is True

    def test_case_insensitive(self):
        assert contains_ad("ERID: 123456") is True

    def test_empty_text_safe(self):
        assert contains_ad("") is False
        assert contains_ad(None) is False  # type: ignore[arg-type]


class TestKeywordDisabled:
    def test_no_keywords_means_no_filter(self, monkeypatch):
        monkeypatch.setattr(type(settings), "parsed_ad_keywords",
                            property(lambda self: []))
        assert contains_ad("подписывайтесь на рекламу") is False
