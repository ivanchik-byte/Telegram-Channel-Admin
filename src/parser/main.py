import os
import asyncio
from telethon import TelegramClient, events
from src.core.config import settings
from src.core.logger import logger
from src.parser.handlers import new_message_handler

from arq import create_pool
from arq.connections import RedisSettings

SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'anon')

async def check_force_parse(client: TelegramClient, channels: list):
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        logger.info("Started background task to check for force_parse requests...")
        while True:
            try:
                val = await redis.get('force_parse')
                if val:
                    await redis.delete('force_parse')
                    val_str = val.decode('utf-8')
                    limit = 5
                    num_channels = 0
                    time_offset = ''

                    if '|' in val_str:
                        parts = val_str.split('|')
                        limit = int(parts[0]) if parts[0].isdigit() else 5
                        if len(parts) > 1:
                            num_channels = int(parts[1]) if parts[1].isdigit() else 0
                        if len(parts) > 2:
                            time_offset = parts[2]
                    else:
                        # Fallback for old format
                        limit = int(val_str) if val_str.isdigit() else 5

                    offset_date = None
                    if time_offset:
                        from src.core.utils import parse_time_suffix
                        from datetime import datetime, timezone
                        delta = parse_time_suffix(time_offset)
                        if delta:
                            offset_date = datetime.now(timezone.utc) - delta
                            limit = None # Fetch ALL messages since offset_date
                    
                    logger.info(f"Manual parsing triggered! time_offset={time_offset}, limit={limit}, num_channels={num_channels}.")
                    
                    target_channels = channels
                    if num_channels > 0 and num_channels < len(channels):
                        import random
                        target_channels = random.sample(channels, num_channels)
                    
                    class DummyEvent:
                        def __init__(self, msg, c):
                            self.message = msg
                            self.chat_id = msg.chat_id
                            self.id = msg.id
                            self.chat = msg.chat
                            self.client = c

                    parsed_count = 0
                    for channel in target_channels:
                        try:
                            logger.info(f"Fetching from {channel}...")
                            kwargs = {'limit': limit}
                            if offset_date:
                                kwargs['offset_date'] = offset_date
                                kwargs['reverse'] = True # to fetch from old to new, but we might want new to old
                                # Actually, offset_date in iter_messages gets messages older than the date. 
                                # We want messages NEWER than the date. 
                                # Let's fetch until we hit a message older than offset_date.
                                kwargs.pop('offset_date')
                                kwargs.pop('reverse', None)
                            
                            async for msg in client.iter_messages(channel, **kwargs):
                                if offset_date and msg.date and msg.date < offset_date:
                                    break # Stop fetching when we reach messages older than our offset

                                if msg.message:
                                    res = await new_message_handler(DummyEvent(msg, client))
                                    if res is not None:
                                        parsed_count += 1
                        except Exception as e:
                            logger.error(f"Error parsing channel {channel}: {e}")
                    
                    # Send notification to MODERATOR_CHAT_ID via Telegram Bot API
                    import httpx
                    try:
                        async with httpx.AsyncClient() as http_client:
                            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
                            text = f"Ручной парсинг успешно завершен. Импортировано новых уникальных постов: {parsed_count}."
                            await http_client.post(url, json={
                                "chat_id": settings.effective_moderator_chat_id,
                                "text": text
                            })
                    except Exception as err:
                        logger.error(f"Failed to send parsing finished notification: {err}")
            except Exception as e:
                logger.error(f"Error checking force_parse: {e}")
            await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"Fatal error in check_force_parse: {e}")

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
    
    client.loop.create_task(check_force_parse(client, channels))
    
    try:
        await client.run_until_disconnected()
    finally:
        if hasattr(client, 'redis_pool') and client.redis_pool:
            await client.redis_pool.close()
            logger.info("Redis pool closed.")

if __name__ == "__main__":
    asyncio.run(main())
