import asyncio
import os
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from src.core.config import settings
from src.core.logger import logger

async def main():
    # Настройки из вашего .env
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    session_file = 'data/anon'

    client = TelegramClient(session_file, api_id, api_hash)
    await client.start()

    logger.info("Подключаемся к Telegram для автоматической подписки...")

    for channel in settings.DONOR_CHANNEL_IDS:
        channel_str = str(channel).strip()
        try:
            if "t.me/+" in channel_str or "t.me/joinchat/" in channel_str:
                # Приватная ссылка
                hash_part = channel_str.split("/")[-1].replace("+", "")
                await client(ImportChatInviteRequest(hash_part))
                logger.info(f"Успешно присоединились по ссылке: {channel_str}")
            else:
                # Публичный канал (юзернейм) или уже известный ID
                await client(JoinChannelRequest(channel))
                logger.info(f"Успешно подписались на канал: {channel_str}")
            
            # Небольшая пауза, чтобы не получить бан от Telegram за флуд
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Не удалось подписаться на {channel_str}: {e}")

    await client.disconnect()
    logger.info("Процесс подписки завершен.")

if __name__ == '__main__':
    asyncio.run(main())
