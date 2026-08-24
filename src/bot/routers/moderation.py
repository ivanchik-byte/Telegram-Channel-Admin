import os
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from src.core.logger import logger
from src.core.config import settings
from src.core.constants import TG_SAFE_MESSAGE_LIMIT, TG_MESSAGE_LIMIT
from src.core.utils import format_telegram_html, strip_html
from src.core.i18n import i18n
from src.database.engine import async_session_maker
from src.database.repository import PostRepository, SettingsRepository
from src.database.models import ProcessedPost

from src.bot.filters import IsModeratorFilter
from src.bot.states import MediaReplacement, TextReplacement, AIEditState
from src.bot.keyboards import kb_variants
from src.bot.messaging import (
    send_media_with_caption,
    send_long_message,
    send_mod_card_to_chat,
    build_mod_card_keyboard,
    cleanup_media,
)


router = Router()


def _parse_post_id(callback_data: str) -> int | None:
    """Safely extracts post ID from callback_data like 'publish_123' or 'change_media_123'."""
    parts = callback_data.rsplit("_", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


async def _apply_interval_after_moderation(session):
    import random
    from datetime import datetime, timezone, timedelta

    bot_settings = await SettingsRepository.get_settings(session)
    if bot_settings.interval_max > 0:
        delay = random.randint(bot_settings.interval_min, bot_settings.interval_max)
        next_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await SettingsRepository.update_settings(session, next_post_time=next_time)
        logger.info(f"[Bot] Интервал запущен: следующий пост будет через {delay} секунд.")
    else:
        await SettingsRepository.update_settings(session, next_post_time=None)


@router.callback_query(F.data.startswith("publish_"), IsModeratorFilter())
async def process_publish(callback: CallbackQuery, bot: Bot):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        # Verify there is something to publish BEFORE flipping the status,
        # otherwise a failed check would leave the post stuck as 'published'
        existing = await PostRepository.get_post_by_id(session, post_id)
        if not existing or existing.status != 'moderating':
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return
        if not existing.rewritten_text:
            await callback.answer(i18n.get('msg_no_text_to_publish'), show_alert=True)
            return

        post = await PostRepository.atomic_status_update(session, post_id, 'moderating', 'published')
        if not post:
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

        text_to_publish = post.rewritten_text

        try:
            # Publish to target channel (senders take RAW text and format per chunk)
            published_with_media = False
            if post.media_path and post.media_type:
                abs_path = os.path.abspath(post.media_path)
                if os.path.exists(abs_path):
                    media_file = FSInputFile(abs_path)
                    await send_media_with_caption(
                        bot, settings.TARGET_CHANNEL_ID,
                        post.media_type, media_file, text_to_publish
                    )
                    published_with_media = True
                else:
                    logger.warning(f"[Bot] Media file not found: {abs_path}. Publishing as text.")
            if not published_with_media:
                await send_long_message(bot, settings.TARGET_CHANNEL_ID, text_to_publish)

            # Edit moderator message — escape user content before embedding in HTML
            action_by = escape(callback.from_user.username or callback.from_user.full_name)
            display_text = format_telegram_html(text_to_publish[:TG_SAFE_MESSAGE_LIMIT])
            new_text = f"{i18n.get('msg_published')}\n{i18n.get('action_by', username=action_by)}\n\n{display_text}"

            try:
                if callback.message.photo or callback.message.video or callback.message.document:
                    await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
                else:
                    await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
            except Exception as edit_err:
                logger.warning(f"[Bot] Edit message failed with HTML, falling back to plain text: {edit_err}")
                plain_new_text = strip_html(new_text)
                if callback.message.photo or callback.message.video or callback.message.document:
                    await callback.message.edit_caption(caption=plain_new_text, reply_markup=None)
                else:
                    await callback.message.edit_text(text=plain_new_text, reply_markup=None)

            cleanup_media(post.media_path, "публикации")

            await _apply_interval_after_moderation(session)

            await callback.answer(i18n.get('msg_published_alert'))

            logger.info(f"[Bot] Пост {post_id} опубликован в канал.")
        except Exception as e:
            # Revert status back to moderating so we don't block the post permanently
            async with async_session_maker() as rollback_session:
                await PostRepository.update_status(rollback_session, post_id, 'moderating', required_current_status='published')
            logger.error(f"[Bot] Ошибка публикации поста {post_id}: {e}")
            await callback.answer(i18n.get('publish_error', error=escape(str(e))), show_alert=True)


def strip_html(value: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', value)


@router.callback_query(F.data.startswith("reject_"), IsModeratorFilter())
async def process_reject(callback: CallbackQuery):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_status_update(session, post_id, 'moderating', 'rejected')
        if not post:
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

        action_by = escape(callback.from_user.username or callback.from_user.full_name)
        display_text = format_telegram_html((post.rewritten_text or "")[:TG_MESSAGE_LIMIT])
        new_text = f"{i18n.get('msg_rejected')}\n{i18n.get('action_by', username=action_by)}\n\n{display_text}"

        try:
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
        except Exception as edit_err:
            logger.warning(f"[Bot] Edit message failed with HTML, falling back to plain text: {edit_err}")
            plain_new_text = strip_html(new_text)
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.edit_caption(caption=plain_new_text, reply_markup=None)
            else:
                await callback.message.edit_text(text=plain_new_text, reply_markup=None)

        cleanup_media(post.media_path, "отклонения")

        await _apply_interval_after_moderation(session)

        await callback.answer(i18n.get('msg_rejected_alert'))
        logger.info(f"[Bot] Пост {post_id} отклонен.")


@router.message(Command("mod"), IsModeratorFilter())
async def cmd_mod(message: Message, bot: Bot):
    """Alias for the moderation button, documented in README/COMMANDS."""
    await reply_moderation(message, bot)


@router.message(F.text.in_(kb_variants('kb_moderation')), IsModeratorFilter())
async def reply_moderation(message: Message, bot: Bot):
    from sqlalchemy import select, func

    async with async_session_maker() as session:
        # Get first post ready for moderation
        stmt = select(ProcessedPost).where(ProcessedPost.status == 'moderating').order_by(ProcessedPost.id.asc()).limit(1)
        result = await session.execute(stmt)
        post = result.scalars().first()

        if not post:
            # Check if there are posts in queued or accumulated status
            stmt = select(ProcessedPost).where(
                ProcessedPost.status.in_(['queued', 'accumulated'])
            ).order_by(ProcessedPost.id.asc()).limit(1)
            result = await session.execute(stmt)
            next_post = result.scalars().first()

            if next_post:
                # Atomically update to ai_processing (with stale-lock timestamp)
                post_locked = await PostRepository.atomic_status_update(
                    session, next_post.id, ['queued', 'accumulated'], 'ai_processing', set_lock=True
                )
                if post_locked:
                    progress_msg = await message.reply(i18n.get('mod_extracting'))

                    from src.worker.tasks import _call_ai_with_retry
                    from src.core.prompts import get_system_prompt
                    from src.core.clients import get_ai_client

                    ai_client = get_ai_client()
                    bot_settings = await SettingsRepository.get_settings(session)
                    post_lang = getattr(bot_settings, 'post_lang', 'ru')
                    custom_prompt = getattr(bot_settings, 'custom_prompt', None)
                    sys_prompt = get_system_prompt(post_lang, custom_prompt)

                    # Release session lock during network call
                    await session.commit()

                    rewritten = await _call_ai_with_retry(ai_client, post_locked.text, post_locked.id, system_prompt=sys_prompt)

                    if rewritten:
                        async with async_session_maker() as new_session:
                            await PostRepository.update_post_ready_for_moderation(
                                new_session, post_locked.id, rewritten,
                                required_current_status='ai_processing'
                            )
                            # Fetch updated post
                            stmt = select(ProcessedPost).where(ProcessedPost.id == post_locked.id)
                            res = await new_session.execute(stmt)
                            post = res.scalars().first()

                        # Delete the progress message
                        try:
                            await progress_msg.delete()
                        except Exception:
                            pass
                    else:
                        async with async_session_maker() as new_session:
                            await PostRepository.update_status(new_session, post_locked.id, 'failed')
                        await progress_msg.edit_text(i18n.get('mod_ai_failed'))
                        return
                else:
                    # Locked by another process
                    await message.reply(i18n.get('mod_already_processing'))
                    return
            else:
                # No posts at all
                await message.reply(i18n.get('mod_queue_empty'))
                return

        # Count total moderating posts
        count_stmt = select(func.count()).select_from(ProcessedPost).where(ProcessedPost.status == 'moderating')
        total = (await session.execute(count_stmt)).scalar() or 0

    if post:
        await message.reply(i18n.get('mod_remaining', count=total))
        await send_mod_card_to_chat(bot, message.chat.id, post)


@router.callback_query(F.data.startswith("edit_"), IsModeratorFilter())
async def process_edit(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('edit_error_id'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer(i18n.get('edit_post_processed'), show_alert=True)
            return

    await state.set_state(TextReplacement.waiting_for_text)
    await state.update_data(post_id=post_id)
    await callback.message.delete()
    await callback.message.answer(i18n.get('edit_send_new_text', post_id=post_id))
    await callback.message.answer((post.rewritten_text or "")[:4000])


@router.message(TextReplacement.waiting_for_text, IsModeratorFilter())
async def receive_new_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')
    if not post_id or not message.text:
        await message.reply(i18n.get('edit_text_not_received'))
        await state.clear()
        return

    # Allow exiting the state with /cancel
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.reply(i18n.get('action_cancelled'))
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_edit_text(session, post_id, 'moderating', message.text)
        if post:
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            await message.reply(i18n.get('edit_post_not_found'))

    await state.clear()


async def ai_custom_edit(text: str, instruction: str) -> str | None:
    """
    Calls OpenAI to rewrite the text based on custom user instruction.
    """
    from src.core.prompts import get_system_prompt
    from src.core.clients import get_ai_client

    client = get_ai_client()

    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
        post_lang = getattr(bot_settings, 'post_lang', 'ru')
        custom_prompt = getattr(bot_settings, 'custom_prompt', None)

    sys_prompt = get_system_prompt(post_lang, custom_prompt)

    full_edit_prompt = (
        f"{sys_prompt}\n\n---\n\n"
        f"Вот текущий текст поста:\n{text}\n\n---\n\n"
        f"Инструкция по редактированию:\n{instruction}"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": full_edit_prompt}],
            extra_body=settings.AI_EXTRA_BODY or {},
            timeout=60.0
        )
        content = response.choices[0].message.content
        if content:
            from src.core.utils import clean_post_output
            content = clean_post_output(content)
        return content or None
    except Exception as e:
        logger.error(f"[AI Custom Edit] Error: {e}")
        return None


@router.callback_query(F.data.startswith("ai_edit_"), IsModeratorFilter())
async def process_ai_edit(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

    await state.update_data(post_id=post_id, mod_card_message_id=callback.message.message_id)
    await state.set_state(AIEditState.waiting_for_instruction)

    await callback.message.reply(
        i18n.get('ai_edit_prompt', post_id=post_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AIEditState.waiting_for_instruction, IsModeratorFilter())
async def receive_ai_instruction(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')
    mod_card_message_id = data.get('mod_card_message_id')
    instruction = message.text

    if not instruction:
        await message.reply(i18n.get('ai_edit_send_instruction'))
        return

    if instruction.strip() == "/cancel":
        await state.clear()
        await message.reply(i18n.get('ai_edit_cancelled'))
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await message.reply(i18n.get('edit_post_not_found'))
            await state.clear()
            return

    progress_msg = await message.reply(i18n.get('ai_edit_progress'), parse_mode="HTML")

    # Edit the current draft, not the raw donor text
    new_text = await ai_custom_edit(post.rewritten_text or post.text, instruction)

    if not new_text:
        await progress_msg.edit_text(i18n.get('ai_edit_failed'))
        await state.clear()
        return

    # Update database
    async with async_session_maker() as session:
        await PostRepository.atomic_edit_text(session, post_id, 'moderating', new_text)

    await progress_msg.delete()
    await state.clear()

    display_text = format_telegram_html(new_text[:TG_SAFE_MESSAGE_LIMIT])

    try:
        if post.media_path and post.media_type:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=mod_card_message_id,
                caption=display_text,
                reply_markup=build_mod_card_keyboard(post_id),
                parse_mode="HTML"
            )
        else:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=mod_card_message_id,
                text=display_text,
                reply_markup=build_mod_card_keyboard(post_id),
                parse_mode="HTML"
            )
        await message.reply(i18n.get('ai_edit_success'))
    except Exception as e:
        logger.error(f"[Bot] Error updating mod card: {e}")
        # If edit fails, we just send a new mod card
        async with async_session_maker() as session:
            updated_post = await PostRepository.get_post_by_id(session, post_id)
            if updated_post:
                await send_mod_card_to_chat(bot, message.chat.id, updated_post)


@router.callback_query(F.data.startswith("change_media_"), IsModeratorFilter())
async def process_change_media(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

    await state.update_data(post_id=post_id)
    await callback.message.delete()
    await state.set_state(MediaReplacement.waiting_for_media)
    # Old message is deleted; use answer() since reply() would fail
    await callback.message.answer(
        i18n.get('media_send_prompt', post_id=post_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(MediaReplacement.waiting_for_media, IsModeratorFilter())
async def receive_new_media(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')

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

    # Allow exiting the state with /cancel
    if not media_type and message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.reply(i18n.get('action_cancelled'))
        return

    if not media_type:
        await message.reply(i18n.get('media_send_please'))
        return

    os.makedirs('data/media', exist_ok=True)
    temp_filename = f"media_{post_id}_{int(message.date.timestamp())}"

    try:
        file_info = await bot.get_file(file_id)
        file_ext = os.path.splitext(file_info.file_path)[1]
        new_filename = f"{temp_filename}{file_ext}"
        media_path = os.path.join('data/media', new_filename)
        await bot.download_file(file_info.file_path, media_path)
    except Exception as e:
        await message.reply(i18n.get('media_save_failed', error=e))
        await state.clear()
        return

    async with async_session_maker() as session:
        # Fetch the old media path before it is overwritten
        old_post = await PostRepository.get_post_by_id(session, post_id)
        old_media_path = old_post.media_path if old_post else None
        post = await PostRepository.atomic_update_media(session, post_id, 'moderating', media_path, media_type)
        if post:
            from src.core.utils import delete_media_file
            if old_media_path and old_media_path != media_path:
                delete_media_file(old_media_path)
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            # Update failed (post already processed) — don't leak the temp file
            try:
                os.remove(media_path)
            except OSError:
                pass
            await message.reply(i18n.get('edit_post_not_found'))

    await state.clear()
