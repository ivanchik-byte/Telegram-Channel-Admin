import hashlib
import re
from html import escape
from telethon import events
from src.core.logger import logger
from src.database.engine import async_session_maker
from src.database.repository import PostRepository


def calculate_post_hash(text: str) -> str:
    """Normalizes and hashes post text for deduplication."""
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


async def new_message_handler(event: events.NewMessage.Event):
    text = event.message.message or ""

    if not text.strip():
        logger.info("[Parser] Получен пустой медиа-пост без текста. Игнорируем.")
        return

    channel_id = event.chat_id
    message_id = event.id
    post_hash = calculate_post_hash(text)

    async with async_session_maker() as session:
        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=channel_id,
            message_id=message_id,
            post_hash=post_hash,
            text=text,
            status='queued'
        )

        if not post_id:
            return

    logger.info(f"[Parser] Перехвачен новый пост из {channel_id}. Хэш: {post_hash}. Отправлен в очередь.")

    # Enqueue to Arq — если падает, откатываем статус чтобы пост не завис в 'queued' вечно
    pool = event.client.redis_pool
    try:
        await pool.enqueue_job('process_post_task', post_id)
    except Exception as e:
        logger.error(f"[Parser] Ошибка отправки в Redis (Arq): {e}. Пост {post_id} помечен как failed.")
        async with async_session_maker() as rollback_session:
            await PostRepository.update_status(rollback_session, post_id, 'failed')
