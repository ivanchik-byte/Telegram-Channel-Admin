from html import escape
import os
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, BaseFilter, CommandObject
from src.core.logger import logger
from src.core.config import settings
from src.core.constants import TG_SAFE_MESSAGE_LIMIT, TG_MESSAGE_LIMIT
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from src.core.i18n import i18n


class IsModeratorFilter(BaseFilter):
    async def __call__(self, event) -> bool:
        if isinstance(event, Message):
            if not event.from_user:
                return False
            chat_id = event.chat.id
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            if not event.from_user:
                return False
            chat_id = event.message.chat.id
            user_id = event.from_user.id
        else:
            return False

        is_admin = user_id in settings.ADMIN_IDS
        is_right_chat = str(chat_id) == str(settings.MODERATOR_CHAT_ID)

        if is_right_chat and not is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer(i18n.get('msg_access_denied'), show_alert=True)
            return False

        return is_admin and is_right_chat


def _parse_post_id(callback_data: str) -> int | None:
    """Safely extracts post ID from callback_data like 'publish_123'."""
    parts = callback_data.split("_", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


def _cleanup_media(media_path: str | None, action: str) -> None:
    """Helper to clean up media files after publication or rejection."""
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
            logger.info(f"[Bot] Файл {media_path} удален после {action}.")
        except Exception as e:
            logger.error(f"[Bot] Не удалось удалить файл {media_path}: {e}")


router = Router()

@router.callback_query(F.data.startswith("publish_"), IsModeratorFilter())
async def process_publish(callback: CallbackQuery, bot: Bot):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_status_update(session, post_id, 'moderating', 'published')
        if not post:
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

        text_to_publish = post.rewritten_text
        if not text_to_publish:
            await callback.answer(i18n.get('msg_no_text_to_publish'), show_alert=True)
            return

        try:
            # Publish to target channel (plain text, no HTML parsing)
            if post.media_path and post.media_type:
                media_file = FSInputFile(post.media_path)
                if post.media_type == 'photo':
                    await bot.send_photo(chat_id=settings.TARGET_CHANNEL_ID, photo=media_file, caption=text_to_publish, parse_mode=None)
                elif post.media_type == 'video':
                    await bot.send_video(chat_id=settings.TARGET_CHANNEL_ID, video=media_file, caption=text_to_publish, parse_mode=None)
                else:
                    await bot.send_document(chat_id=settings.TARGET_CHANNEL_ID, document=media_file, caption=text_to_publish, parse_mode=None)
            else:
                await bot.send_message(chat_id=settings.TARGET_CHANNEL_ID, text=text_to_publish, parse_mode=None)

            # Edit moderator message — escape user content before embedding in HTML
            display_text = escape(text_to_publish[:TG_SAFE_MESSAGE_LIMIT])
            new_text = f"{i18n.get('msg_published')}\n\n{display_text}"
            
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")

            _cleanup_media(post.media_path, "публикации")

            await callback.answer(i18n.get('msg_published_alert'))

            logger.info(f"[Bot] Пост {post_id} опубликован в канал.")
        except Exception as e:
            logger.error(f"[Bot] Ошибка публикации поста {post_id}: {e}")
            await callback.answer(i18n.get('msg_publish_error'), show_alert=True)

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

        display_text = escape((post.rewritten_text or "")[:TG_MESSAGE_LIMIT])
        new_text = f"{i18n.get('msg_rejected')}\n\n{display_text}"
        
        if callback.message.photo or callback.message.video or callback.message.document:
            await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
            
        _cleanup_media(post.media_path, "отклонения")

        await callback.answer(i18n.get('msg_rejected_alert'))
        logger.info(f"[Bot] Пост {post_id} отклонен.")

@router.callback_query(F.data.startswith("edit_"), IsModeratorFilter())
async def process_edit(callback: CallbackQuery):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer(i18n.get('msg_already_processed'), show_alert=True)
            return

        instruction = i18n.get('msg_edit_instruction', post_id=post_id)
        await callback.message.answer(instruction, parse_mode="HTML")
        # Plain text — no parse_mode, safe without escaping
        await callback.message.answer((post.rewritten_text or "")[:TG_MESSAGE_LIMIT])
        await callback.answer()

@router.message(Command("edit"), IsModeratorFilter())
async def process_edit_command(message: Message, command: CommandObject):
    if not command.args:
        await message.reply(i18n.get('msg_edit_wrong_format'))
        return

    parts = command.args.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(i18n.get('msg_edit_wrong_format'))
        return

    try:
        post_id = int(parts[0])
    except ValueError:
        await message.reply(i18n.get('msg_edit_id_not_number'))
        return

    new_text = parts[1].strip()

    async with async_session_maker() as session:
        post = await PostRepository.atomic_edit_text(session, post_id, 'moderating', new_text)
        if not post:
            await message.reply(i18n.get('msg_edit_post_not_found'))
            return

        # Send new moderation card — escape user content before embedding in HTML
        display_text = escape(new_text[:TG_SAFE_MESSAGE_LIMIT])
        text_to_send = f"{i18n.get('card_edited_post', channel_id=post.source_channel_id)}\n\n{display_text}"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=i18n.get('btn_publish'), callback_data=f"publish_{post_id}"),
                InlineKeyboardButton(text=i18n.get('btn_reject'), callback_data=f"reject_{post_id}")
            ],
            [
                InlineKeyboardButton(text=i18n.get('btn_edit'), callback_data=f"edit_{post_id}")
            ]
        ])

        if post.media_path and os.path.exists(post.media_path):
            media_file = FSInputFile(post.media_path)
            if post.media_type == 'photo':
                await message.answer_photo(photo=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
            elif post.media_type == 'video':
                await message.answer_video(video=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer_document(document=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(text_to_send, reply_markup=keyboard, parse_mode="HTML")
            
        await message.reply(i18n.get('msg_edit_success'))
        logger.info(f"[Bot] Текст поста {post_id} изменен вручную модератором.")


# --- Admin Commands ---

from src.database.repository import SettingsRepository
from src.core.utils import parse_time_suffix
from datetime import datetime, timezone, timedelta
from src.database.models import ProcessedPost
from sqlalchemy import select, update, delete

@router.message(Command("mode"), IsModeratorFilter())
async def cmd_mode(message: Message, command: CommandObject):
    if not command.args or command.args.lower() not in ['auto', 'curation']:
        await message.reply("Использование: /mode auto | curation\n\nauto: 1 пост на модерации, 5 в очереди.\ncuration: тихий сбор всех постов (команда /best).")
        return
        
    new_mode = command.args.lower()
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, mode=new_mode)
        
    await message.reply(f"Режим успешно изменен на: <b>{new_mode}</b>", parse_mode="HTML")


@router.message(Command("best"), IsModeratorFilter())
async def cmd_best(message: Message, command: CommandObject):
    hours = 12
    if command.args:
        try:
            delta = parse_time_suffix(command.args)
            if delta:
                hours = int(delta.total_seconds() / 3600)
            else:
                hours = int(command.args)
        except ValueError:
            await message.reply("Неверный формат времени. Пример: /best 12h")
            return

    from arq import create_pool
    from src.core.config import get_redis_settings
    
    redis = await create_pool(get_redis_settings())
    try:
        await redis.enqueue_job('find_best_post_task', hours)
        await message.reply(f"Запущен поиск лучшего поста за последние {hours} часов. Ожидайте...")
    finally:
        await redis.close()


@router.message(Command("interval"), IsModeratorFilter())
async def cmd_interval(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Использование: /interval <min>-<max> (например: /interval 20m-50m)\nИли /interval 0 для отключения.")
        return
        
    args = command.args.strip()
    if args == "0":
        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, interval_min=0, interval_max=0)
        await message.reply("Интервал отключен.")
        return
        
    parts = args.split("-")
    try:
        min_delta = parse_time_suffix(parts[0])
        max_delta = parse_time_suffix(parts[1]) if len(parts) > 1 else min_delta
        
        if not min_delta or not max_delta:
            raise ValueError()
            
        interval_min = int(min_delta.total_seconds() / 60)
        interval_max = int(max_delta.total_seconds() / 60)
        
        if interval_min > interval_max:
            interval_min, interval_max = interval_max, interval_min
            
        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, interval_min=interval_min, interval_max=interval_max)
            
        await message.reply(f"Интервал выдачи постов установлен: от {interval_min} до {interval_max} минут.")
    except Exception:
        await message.reply("Неверный формат. Пример: /interval 20m-50m")


@router.message(Command("pause"), IsModeratorFilter())
async def cmd_pause(message: Message, command: CommandObject):
    pause_until = None
    msg_text = "Бот поставлен на ВЕЧНУЮ паузу. Парсер отключен.\nДля запуска используйте /resume"
    
    if command.args:
        delta = parse_time_suffix(command.args)
        if delta:
            pause_until = datetime.now(timezone.utc) + delta
            msg_text = f"Бот поставлен на паузу до {pause_until.strftime('%Y-%m-%d %H:%M:%S')} UTC."
        else:
            await message.reply("Неверный формат времени. Пример: /pause 60m")
            return
            
    async with async_session_maker() as session:
        # Для вечной паузы ставим год +100
        if not pause_until:
            pause_until = datetime.now(timezone.utc) + timedelta(days=36500)
        await SettingsRepository.update_settings(session, pause_until=pause_until)
        
    await message.reply(msg_text)


@router.message(Command("resume"), IsModeratorFilter())
async def cmd_resume(message: Message):
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, pause_until=None)
    await message.reply("Бот возобновил работу (пауза снята).")


@router.message(Command("status"), IsModeratorFilter())
async def cmd_status(message: Message):
    async with async_session_maker() as session:
        settings = await SettingsRepository.get_settings(session)
        mod_count, queued_count = await PostRepository.get_queue_counts(session)
        
        # Считаем accumulated
        stmt = select(ProcessedPost.id).where(ProcessedPost.status == 'accumulated')
        acc_result = await session.execute(stmt)
        accumulated_count = len(acc_result.all())
        
        lines = [
            f"<b>Режим:</b> {settings.mode}",
            f"<b>Интервал:</b> {settings.interval_min}-{settings.interval_max} мин.",
        ]
        
        now = datetime.now(timezone.utc)
        if settings.pause_until and settings.pause_until > now:
            lines.append(f"<b>Пауза до:</b> {settings.pause_until.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            lines.append("<b>Пауза:</b> Нет")
            
        if settings.next_post_time and settings.next_post_time > now:
            delay = int((settings.next_post_time - now).total_seconds() / 60)
            lines.append(f"<b>След. пост через:</b> ~{delay} мин")
            
        lines.append("")
        lines.append(f"<b>На модерации:</b> {mod_count} / 1")
        lines.append(f"<b>В очереди (auto):</b> {queued_count} / 5")
        lines.append(f"<b>В корзине (curation):</b> {accumulated_count}")
        
        await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("clear"), IsModeratorFilter())
async def cmd_clear(message: Message):
    async with async_session_maker() as session:
        # Удаляем или переводим в failed все queued и accumulated
        stmt = update(ProcessedPost).where(
            ProcessedPost.status.in_(['queued', 'accumulated'])
        ).values(status='failed')
        await session.execute(stmt)
        await session.commit()
    await message.reply("Очередь и корзина полностью очищены.")
