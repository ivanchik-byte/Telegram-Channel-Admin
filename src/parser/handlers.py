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

        from sqlalchemy import select
        from src.database.models import ProcessedPost
        
        dup_stmt = select(ProcessedPost.id).where(ProcessedPost.post_hash == post_hash).limit(1)
        dup_result = await session.execute(dup_stmt)
        is_duplicate = dup_result.scalar() is not None
        
        status = 'duplicate_content' if is_duplicate else 'seen'

        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=channel_id,
            message_id=message_id,
            post_hash=post_hash,
            text=text,
            status=status
        )

        if not post_id:
            return
        
        if is_duplicate:
            logger.info(f"[Parser] Пост {channel_id}:{message_id} - дубликат контента (отправлен в очередь).")
        else:
            logger.info(f"[Parser] Перехвачен новый пост из {channel_id}. Хэш: {post_hash}.")
        
        # Mark queued before Arq
        await PostRepository.update_status(session, post_id, 'queued')
        
        # Enqueue to Arq
        pool = event.client.redis_pool
        try:
            await pool.enqueue_job('process_post_task', post_id)
        except Exception as e:
            logger.error(f"[Parser] Ошибка отправки в Redis (Arq): {e}")
