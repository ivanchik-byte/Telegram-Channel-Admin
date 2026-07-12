import os
import asyncio
from telethon import TelegramClient, events
from src.core.config import settings
from src.core.logger import logger
from src.parser.handlers import new_message_handler

from arq import create_pool
from arq.connections import RedisSettings

SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'anon')

async def main():
    if not os.path.exists(f"{SESSION_FILE}.session"):
        logger.error(f"Session file not found at {SESSION_FILE}.session. Please run login.py first.")
        return

    # Check parsed channels
    channels = settings.parsed_channels
    if not channels:
        import sys
        sys.exit("CHANNELS_TO_TRACK is empty")

    client = TelegramClient(SESSION_FILE, settings.API_ID, settings.API_HASH)
    
    # Initialize redis pool and attach to client
    client.redis_pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    
    # Add handler for specific channels
    client.add_event_handler(
        new_message_handler, 
        events.NewMessage(chats=channels)
    )

    logger.info("Starting Telegram parser client...")
    await client.start()
    logger.info(f"Parser is running and tracking channels: {channels}")
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
