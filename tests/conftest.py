"""Provides required env vars BEFORE any src import so that
src.core.config.Settings() never fails, even without a .env file.
Real values from an existing .env still win (setdefault semantics).
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "test_hash")
os.environ.setdefault("CHANNELS_TO_TRACK", "@test_channel")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test-token")
os.environ.setdefault("TARGET_CHANNEL_ID", "-1001234567890")
os.environ.setdefault("AI_API_KEY", "sk-test")
