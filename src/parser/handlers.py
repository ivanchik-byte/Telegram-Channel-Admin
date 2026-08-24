import hashlib
import re
from html import escape
from telethon import events
from src.core.logger import logger
from src.core.i18n import i18n
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
        logger.info("[Parser] Received empty media post without text. Ignoring.")
        return

    channel_id = event.chat_id
    message_id = event.id

    # Hash the original text BEFORE appending hidden links: link sets differ
    # between reposts of the same content and would break deduplication
    post_hash = calculate_post_hash(text)

    # Extract hidden links
    links = []
    if event.message.entities:
        from telethon.tl.types import MessageEntityTextUrl
        for ent in event.message.entities:
            if isinstance(ent, MessageEntityTextUrl):
                links.append(ent.url)

    if links:
        unique_links = list(set(links))
        text += f"\n\n{i18n.get('parser_hidden_links')}\n" + "\n".join(unique_links)

    source_link = get_telegram_link(event)

    async with async_session_maker() as session:
        settings = await SettingsRepository.get_settings(session)

        # Check global pause
        if settings.pause_until and settings.pause_until > datetime.now(timezone.utc):
            logger.info(f"[Parser] Bot is paused until {settings.pause_until}. Ignoring post.")
            return

        mode = settings.mode

        # Check advertising
        from src.core.adfilter import contains_ad
        if contains_ad(text):
            logger.info(f"[Parser] Post {message_id} from {channel_id} filtered as ad during parsing.")
            initial_status = 'filtered_ad'
        elif mode == 'auto':
            # Check limits: 1 slot for moderation + queue_limit slots for the queue.
            # Single check right before insert; duplicate inserts are still protected
            # by the UPSERT on (source_channel_id, source_message_id).
            mod_count, queued_count = await PostRepository.get_queue_counts(session)
            if mod_count >= 1 and queued_count >= settings.queue_limit:
                logger.info(f"[Parser] Queue is full ({mod_count} in moderation, {queued_count} in queue). Ignoring post {message_id}.")
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
            logger.info(f"[Parser] Downloading media ({media_type}) for post {message_id}...")
            try:
                media_path = await event.message.download_media(file='data/media/')
                logger.info(f"[Parser] Media saved: {media_path}")
            except Exception as e:
                logger.error(f"[Parser] Error downloading media for post {message_id}: {e}")
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

    logger.info(f"[Parser] Intercepted new post from {channel_id}. Hash: {post_hash}. Saved with status: {initial_status}.")

    if initial_status == 'queued':
        # Enqueue to Arq
        pool = event.client.redis_pool
        try:
            await pool.enqueue_job('process_post_task', post_id)
        except Exception as e:
            logger.error(f"[Parser] Error sending to Redis (Arq): {e}. Post {post_id} marked as failed.")
            async with async_session_maker() as rollback_session:
                await PostRepository.update_status(rollback_session, post_id, 'failed')
    return post_id
