"""Test suite for Telegram-Channel-Admin.

Covers the pure/hard logic: message splitting, HTML sanitizing, AI output
cleaning, ad filtering, i18n dictionary consistency and media-file safety.

Run locally:  python -m pytest tests/ -v
In docker:    docker compose run --rm bot python -m pytest tests/ -v
"""
