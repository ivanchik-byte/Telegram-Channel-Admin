from arq.connections import RedisSettings
from src.core.config import settings
from src.worker.tasks import process_post_task
from src.core.logger import logger

from aiogram import Bot

async def startup(ctx):
    logger.info("Arq worker is starting...")
    async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
        await bot.get_me() # Validate token, throws on error

async def shutdown(ctx):
    logger.info("Arq worker is shutting down...")

class WorkerSettings:
    functions = [process_post_task]
    on_startup = startup
    on_shutdown = shutdown
    # Parse DSN (like redis://redis:6379/0) to RedisSettings
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
