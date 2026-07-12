import asyncio
from aiogram import Bot, Dispatcher
from src.core.config import settings
from src.core.logger import logger
from src.bot.handlers import router


async def main():
    logger.info("Starting Telegram Moderator Bot...")

    if not settings.ADMIN_IDS:
        logger.error("ADMIN_IDS is empty. Refusing to start.")
        return

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
