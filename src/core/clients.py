"""Process-wide singletons for the bot process (worker uses ctx instead).

Creating a new AsyncOpenAI / arq pool per request leaks connection pools;
both clients are cheap to share and safe to reuse across event-loop tasks.
"""
from openai import AsyncOpenAI

from src.core.config import settings

_ai_client: AsyncOpenAI | None = None
_redis_pool = None


def get_ai_client() -> AsyncOpenAI:
    global _ai_client
    if _ai_client is None:
        _ai_client = AsyncOpenAI(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
    return _ai_client


async def get_redis_pool():
    global _redis_pool
    if _redis_pool is None:
        from arq import create_pool
        from arq.connections import RedisSettings
        _redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    return _redis_pool
