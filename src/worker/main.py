from arq.connections import RedisSettings
from src.core.config import settings
from src.worker.tasks import process_post_task, find_best_post_task, clean_old_posts_cron, requeue_stuck_posts_cron
from src.core.logger import logger
from arq.cron import cron

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI


async def startup(ctx):
    from src.core.constants import APP_VERSION
    logger.info(f"Arq worker v{APP_VERSION} is starting...")
    from src.database.engine import init_db, async_session_maker
    from src.database.repository import SettingsRepository
    await init_db()

    # Sync UI language for worker-sent notifications (same rationale as the bot)
    async with async_session_maker() as session:
        await SettingsRepository.sync_i18n_language(session)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    ctx['bot'] = bot
    await bot.get_me()  # Validate token, throws on error

    # AI client created once at startup, shared across all tasks via ctx
    ctx['ai_client'] = AsyncOpenAI(
        api_key=settings.AI_API_KEY,
        base_url=settings.AI_BASE_URL,
        timeout=60.0,
        max_retries=2
    )
    logger.info(f"AI client initialized with model '{settings.AI_MODEL}' on endpoint '{settings.AI_BASE_URL}'.")


async def shutdown(ctx):
    logger.info("Arq worker is shutting down...")
    if 'bot' in ctx:
        await ctx['bot'].session.close()


class WorkerSettings:
    functions = [process_post_task, find_best_post_task, clean_old_posts_cron, requeue_stuck_posts_cron]
    cron_jobs = [
        cron(clean_old_posts_cron, minute=0, hour=3),  # daily at 03:00 UTC
        # Reaper: unstick posts stuck in 'ai_processing' after a crash
        cron(requeue_stuck_posts_cron, minute=set(range(0, 60, 15))),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 5       # max retries per task
    job_timeout = 300   # 5 minutes — timeout per task
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
