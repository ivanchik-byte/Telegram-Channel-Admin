from arq.connections import RedisSettings
from src.core.config import settings
from src.worker.tasks import process_post_task, find_best_post_task, clean_old_posts_cron, worker_heartbeat_cron
from src.core.logger import logger
from arq.cron import cron

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI


async def startup(ctx):
    logger.info("Arq worker is starting...")
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ctx['bot'] = bot
    await bot.get_me()  # Validate token, throws on error

    # AI client created once at startup, shared across all tasks via ctx
    ctx['ai_client'] = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
    logger.info("AI client initialized.")


async def shutdown(ctx):
    logger.info("Arq worker is shutting down...")
    if 'bot' in ctx:
        await ctx['bot'].session.close()


class WorkerSettings:
    functions = [process_post_task, find_best_post_task, clean_old_posts_cron, worker_heartbeat_cron]
    cron_jobs = [
        cron(clean_old_posts_cron, minute=0, hour=3), # run daily at 03:00 UTC
        cron(worker_heartbeat_cron, second={0, 15, 30, 45}) # run every 15 seconds
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 5       # максимум попыток для каждой задачи
    job_timeout = 300   # 5 минут — таймаут на одну задачу
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
