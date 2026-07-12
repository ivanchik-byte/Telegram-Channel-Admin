from arq.connections import RedisSettings
from src.core.config import settings
from src.worker.tasks import process_post_task
from src.core.logger import logger

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

async def startup(ctx):
    logger.info("Arq worker is starting...")
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ctx['bot'] = bot
    await bot.get_me() # Validate token, throws on error

async def shutdown(ctx):
    logger.info("Arq worker is shutting down...")
    if 'bot' in ctx:
        await ctx['bot'].session.close()

class WorkerSettings:
    functions = [process_post_task]
    on_startup = startup
    on_shutdown = shutdown
    # Parse DSN
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
