"""Ad filtering by keyword stems.

Lives outside the worker package so it can be unit-tested (and reused)
without pulling in aiogram/openai dependencies.
"""
from src.core.config import settings


def _stems(keyword: str) -> tuple[str, ...]:
    if len(keyword) <= 4:
        return (keyword,)
    return (keyword, keyword[:-1])


def _match(text_lower: str, form: str) -> bool:
    if len(form) <= 4:
        import re
        return re.search(r"(?<![\w])" + re.escape(form) + r"(?![\w])", text_lower) is not None
    return form in text_lower


def contains_ad(text: str) -> bool:
    if not text or not settings.parsed_ad_keywords:
        return False

    text_lower = text.lower()
    for kw in settings.parsed_ad_keywords:
        for form in _stems(kw):
            if _match(text_lower, form):
                return True
    return False
