import hashlib
import re
from html import escape
from telethon import events
from src.core.logger import logger
from src.database.engine import async_session_maker
from src.database.repository import PostRepository, SettingsRepository
from datetime import datetime, timezone


def calculate_post_hash(text: str) -> str:
    """Normalizes and hashes post text for deduplication."""
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def get_telegram_link(event: events.NewMessage.Event) -> str:
    """Constructs direct link to the Telegram post."""
    chat = event.chat
    message_id = event.id
    if chat and hasattr(chat, 'username') and chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    
    # Fallback to private link structure
    chat_id = event.chat_id
    str_id = str(chat_id)
    if str_id.startswith("-100"):
        clean_id = str_id[4:]
    elif str_id.startswith("-"):
        clean_id = str_id[1:]
    else:
        clean_id = str_id
    return f"https://t.me/c/{clean_id}/{message_id}"


async def new_message_handler(event: events.NewMessage.Event):
    text = event.message.message or ""

    if not text.strip():
        logger.info("[Parser] Получен пустой медиа-пост без текста. Игнорируем.")
        return

    channel_id = event.chat_id
    message_id = event.id
    post_hash = calculate_post_hash(text)
    source_link = get_telegram_link(event)

    async with async_session_maker() as session:
        settings = await SettingsRepository.get_settings(session)
        
        # Check global pause
        if settings.pause_until and settings.pause_until > datetime.now(timezone.utc):
            logger.info(f"[Parser] Бот на паузе до {settings.pause_until}. Игнорируем пост.")
            return

        mode = settings.mode
        
        if mode == 'auto':
            # Check limits
            mod_count, queued_count = await PostRepository.get_queue_counts(session)
            if mod_count >= 1 and queued_count >= 5:
                logger.info(f"[Parser] Очередь переполнена (1 на модерации, 5 в очереди). Игнорируем пост {message_id}.")
                return
            initial_status = 'queued'
        else:
            # curation mode
            initial_status = 'accumulated'

    media_path = None
    media_type = None

    if event.message.media:
        if event.message.photo:
            media_type = 'photo'
        elif event.message.video:
            media_type = 'video'
        elif event.message.document:
            media_type = 'document'
        
        if media_type:
            import os
            os.makedirs('data/media', exist_ok=True)
            logger.info(f"[Parser] Скачивание медиа ({media_type}) для поста {message_id}...")
            try:
                media_path = await event.message.download_media(file='data/media/')
                logger.info(f"[Parser] Медиа сохранено: {media_path}")
            except Exception as e:
                logger.error(f"[Parser] Ошибка при скачивании медиа для поста {message_id}: {e}")
                media_path = None
                media_type = None

    async with async_session_maker() as session:
        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=channel_id,
            message_id=message_id,
            post_hash=post_hash,
            text=text,
            media_path=media_path,
            media_type=media_type,
            source_link=source_link,
            status=initial_status
        )

        if not post_id:
            return None

    logger.info(f"[Parser] Перехвачен новый пост из {channel_id}. Хэш: {post_hash}. Сохранен со статусом: {initial_status}.")

    if initial_status == 'queued':
        # Enqueue to Arq
        pool = event.client.redis_pool
        try:
            await pool.enqueue_job('process_post_task', post_id)
        except Exception as e:
            logger.error(f"[Parser] Ошибка отправки в Redis (Arq): {e}. Пост {post_id} помечен как failed.")
            async with async_session_maker() as rollback_session:
                await PostRepository.update_status(rollback_session, post_id, 'failed')
    return post_id
