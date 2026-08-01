import asyncio
import os
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from src.core.config import settings
from src.core.logger import logger

async def main():
    # Settings from your .env
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    session_file = 'data/anon'

    client = TelegramClient(session_file, api_id, api_hash)
    await client.start()

    logger.info("Connecting to Telegram for automatic subscription...")

    for channel in settings.DONOR_CHANNEL_IDS:
        channel_str = str(channel).strip()
        try:
            if "t.me/+" in channel_str or "t.me/joinchat/" in channel_str:
                # Private link
                hash_part = channel_str.split("/")[-1].replace("+", "")
                await client(ImportChatInviteRequest(hash_part))
                logger.info(f"Successfully joined via link: {channel_str}")
            else:
                # Public channel (username) or already known ID
                await client(JoinChannelRequest(channel))
                logger.info(f"Successfully subscribed to channel: {channel_str}")
            
            # Short pause to avoid Telegram ban for flooding
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Failed to subscribe to {channel_str}: {e}")

    await client.disconnect()
    logger.info("Subscription process completed.")

if __name__ == '__main__':
    asyncio.run(main())
