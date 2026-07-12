import hashlib
import re
from telethon import events
from src.core.logger import logger
from src.database.engine import async_session_maker
from src.database.repository import PostRepository

def calculate_md5(text: str, channel_id: int, message_id: int) -> str:
    # Normalize text
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    if not normalized:
        # Fallback hash for empty text
        hash_input = f"{channel_id}_{message_id}"
    else:
        hash_input = normalized
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

async def new_message_handler(event: events.NewMessage.Event):
    text = event.message.message or ""
    
    if not text.strip():
        logger.info("[Parser] Получен пустой медиа-пост без текста. Игнорируем.")
        return
        
    channel_id = event.chat_id
    message_id = event.id

    post_hash = calculate_md5(text, channel_id, message_id)

    async with async_session_maker() as session:

        # Assume seen initially, handled blindly via insert

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
        
        # Enqueue to Arq
        pool = event.client.redis_pool
        try:
            await pool.enqueue_job('process_post_task', post_id)
        except Exception as e:
            logger.error(f"[Parser] Ошибка отправки в Redis (Arq): {e}")
