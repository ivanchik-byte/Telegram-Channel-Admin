import asyncio
from aiogram import Bot, Dispatcher
from src.core.config import settings
from src.core.logger import logger
from src.bot.handlers import router
async def main():
    logger.info("Starting Telegram Moderator Bot...")
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    if not settings.ADMIN_IDS:
        logger.error("ADMIN_IDS is empty. Refusing to start.")
        return

    dp = Dispatcher()
    
    dp.include_router(router)
    
    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
