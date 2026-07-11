import hashlib
import re
from telethon import events
from src.core.logger import logger
from src.database.engine import async_session_maker
from src.database.repository import PostRepository

def calculate_md5(text: str, channel_id: int, message_id: int) -> str:
    # Normalize text: strip and lower, remove extra whitespaces
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    if not normalized:
        # User requested: "{source_channel_id}_{source_message_id}" MD5 if text is empty
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

        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=channel_id,
            message_id=message_id,
            post_hash=post_hash,
            text=text
        )

        if not post_id:
            logger.info(f"[Parser] Пост проигнорирован: дубликат. Channel: {channel_id}, MsgID: {message_id}")
            return
        
        logger.info(f"[Parser] Перехвачен новый пост из {channel_id}. Хэш: {post_hash}.")
        
        # Update status to queued and strictly commit before enqueueing to Arq
        await PostRepository.update_status(session, post_id, 'queued')
        
        # Enqueue to Arq using client's attached redis pool AFTER all DB commits
        pool = event.client.redis_pool
        try:
            await pool.enqueue_job('process_post_task', post_id)
        except Exception as e:
            logger.error(f"[Parser] Ошибка отправки в Redis (Arq): {e}")
