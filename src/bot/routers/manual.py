"""Manual post creation from the admin's PM. This is the catch-all private-chat
handler and MUST be registered LAST so it doesn't swallow commands, keyboard
buttons or FSM input.
"""
import hashlib
import os
import secrets
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.core.logger import logger
from src.core.i18n import i18n
from src.database.engine import async_session_maker
from src.database.repository import PostRepository, SettingsRepository

from src.bot.filters import IsModeratorFilter


router = Router()


# Only private chats: in group mod chats every moderator message
# longer than 5 chars would otherwise be parsed as a manual post
@router.message(F.chat.type == "private", IsModeratorFilter())
async def handle_manual_post(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state is not None:
        return

    if message.text and message.text.startswith('/'):
        return

    text = message.text or message.caption or ""
    if not text:
        await message.reply(i18n.get('manual_send_text'))
        return

    if len(text.strip()) < 5 and not message.photo and not message.video and not message.document:
        await message.reply(i18n.get('manual_text_short'))
        return

    media_type = None
    file_id = None
    if message.photo:
        media_type = 'photo'
        file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        file_id = message.video.file_id
    elif message.document:
        media_type = 'document'
        file_id = message.document.file_id

    os.makedirs('data/media', exist_ok=True)
    media_path = None
    now_ts = int(datetime.now(timezone.utc).timestamp())
    # 62 random bits: collisions on the unique (channel_id, message_id) constraint
    # are practically impossible, unlike the old 10-digit randint
    dummy_message_id = secrets.randbits(62)
    # Unique filename: two manual posts with media in the same second
    # must not overwrite each other's files
    temp_filename = f"manual_{now_ts}_{dummy_message_id}"

    if file_id and media_type:
        try:
            file_info = await bot.get_file(file_id)
            file_ext = os.path.splitext(file_info.file_path)[1]
            new_filename = f"{temp_filename}{file_ext}"
            media_path = os.path.join('data/media', new_filename)
            logger.info(f"[Bot] Скачивание медиа для ручного поста: {media_path}...")
            await bot.download_file(file_info.file_path, media_path)
        except Exception as e:
            logger.error(f"[Bot] Ошибка при скачивании медиа для ручного поста: {e}")
            await message.reply(i18n.get('manual_download_failed'))
            return

    post_hash = hashlib.md5(
        f"manual_{text}_{now_ts}_{dummy_message_id}".encode('utf-8')
    ).hexdigest()

    async with async_session_maker() as session:
        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=0,
            message_id=dummy_message_id,
            post_hash=post_hash,
            text=text,
            media_path=media_path,
            media_type=media_type,
            source_link=i18n.get('manual_source'),
            status='queued'
        )
        await SettingsRepository.update_settings(session, next_post_time=None)

    if not post_id:
        await message.reply(i18n.get('manual_db_failed'))
        return

    from src.core.clients import get_redis_pool
    redis = await get_redis_pool()
    await redis.enqueue_job('process_post_task', post_id)
    await message.reply(i18n.get('manual_accepted', post_id=post_id))
