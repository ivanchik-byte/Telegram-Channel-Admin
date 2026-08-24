"""Ad filtering by keyword stems.

Lives outside the worker package so it can be unit-tested (and reused)
without pulling in aiogram/openai dependencies.
"""
from src.core.config import settings


def _stems(keyword: str) -> tuple[str, str]:
    """Full keyword plus its stem (keyword minus the last letter).

    Plain substring matching misses Russian inflected forms: genitive
    "рекламы" or instrumental "рекламой" do NOT contain "реклама".
    Matching the stem catches all case forms while staying simple.
    """
    return keyword, keyword[:-1] if len(keyword) > 3 else keyword


def contains_ad(text: str) -> bool:
    if not text or not settings.parsed_ad_keywords:
        return False

    text_lower = text.lower()
    for kw in settings.parsed_ad_keywords:
        # Stem match is intentional for Russian morphology:
        # stem "реклам" matches "реклама", "рекламы", "рекламой", ...
        for form in _stems(kw):
            if form in text_lower:
                return True
    return False
