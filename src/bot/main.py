import asyncio
from aiogram import Bot, Dispatcher
from src.core.config import settings
from src.core.logger import logger
from src.bot.handlers import router
from src.database.engine import init_db


async def main():
    from src.core.constants import APP_VERSION
    logger.info(f"Starting Telegram Moderator Bot v{APP_VERSION}...")

    if not settings.ADMIN_IDS:
        logger.error("ADMIN_IDS is empty. Refusing to start.")
        return

    # Ensure database tables and columns are created
    await init_db()

    # Sync UI language from DB once at startup; later changes go through
    # update_settings -> i18n.set_language explicitly
    from src.database.engine import async_session_maker
    from src.database.repository import SettingsRepository
    async with async_session_maker() as session:
        await SettingsRepository.sync_i18n_language(session)

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Do not drop pending updates so we don't miss moderator clicks during restart
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot)
    finally:
        # Guaranteed cleanup regardless of how we exit (normal stop, ADMIN_IDS check, exception)
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
