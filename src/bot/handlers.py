from html import escape
import os
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, BaseFilter, CommandObject
from src.core.logger import logger
from src.core.config import settings
from src.core.constants import TG_SAFE_MESSAGE_LIMIT, TG_MESSAGE_LIMIT
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from src.core.i18n import i18n
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext


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
        is_right_chat = str(chat_id) == str(settings.MODERATOR_CHAT_ID) or str(chat_id) == str(user_id)

        if is_right_chat and not is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer(i18n.get('msg_access_denied'), show_alert=True)
            return False

        return is_admin and is_right_chat


def get_main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Статус"),
                KeyboardButton(text="Помощь")
            ],
            [
                KeyboardButton(text="Пауза 8ч"),
                KeyboardButton(text="Возобновить")
            ],
            [
                KeyboardButton(text="Сбросить интервал"),
                KeyboardButton(text="Очистить очередь")
            ],
            [
                KeyboardButton(text="Парсить сейчас"),
                KeyboardButton(text="Найти лучший пост")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


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
async def process_edit(callback: CallbackQuery, state: FSMContext):
    post_id = _parse_post_id(callback.data)
    if post_id is None:
        await callback.answer("Ошибка ID", show_alert=True)
        return

    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer("Пост уже обработан", show_alert=True)
            return

    await state.set_state(TextReplacement.waiting_for_text)
    await state.update_data(post_id=post_id)
    await callback.message.delete()
    await callback.message.answer(f"Пришлите новый текст для поста {post_id}:")
    await callback.message.answer((post.rewritten_text or "")[:4000])

@router.message(TextReplacement.waiting_for_text, IsModeratorFilter())
async def receive_new_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post_id = data.get('post_id')
    if not post_id or not message.text:
        await message.reply("Текст не получен или ID потерян. Отмена.")
        await state.clear()
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_edit_text(session, post_id, 'moderating', message.text)
        if post:
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            await message.reply("Пост уже обработан или не найден.")
            
    await state.clear()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in settings.ADMIN_IDS:
        logger.warning(f"Unauthorized user {user_id} tried to use start command.")
        await message.reply(
            f"Доступ запрещен. Ваш Telegram ID: <code>{user_id}</code>. Добавьте его в ADMIN_IDS в файле .env.\n\n"
            f"Если вы нашли этого бота случайно, вы можете ознакомиться с проектом на GitHub:\n"
            f"https://github.com/ivanchik-byte/Telegram-Channel-Admin",
            parse_mode="HTML"
        )
        return
        
    keyboard = get_main_reply_keyboard()
    await message.reply(
        "<b>Привет! Я бот-модератор каналов.</b>\n\n"
        "Используйте кнопки меню внизу экрана для быстрого управления или отправьте команду /help для полной справки.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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
                InlineKeyboardButton(text=i18n.get('btn_edit'), callback_data=f"edit_{post_id}"),
                InlineKeyboardButton(text=i18n.get('btn_change_media'), callback_data=f"change_media_{post_id}")
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

import re
from src.database.repository import SettingsRepository
from src.core.utils import parse_time_suffix, format_seconds_readable
from datetime import datetime, timezone, timedelta
from src.database.models import ProcessedPost
from sqlalchemy import select, update, delete

async def get_status_data():
    async with async_session_maker() as session:
        settings = await SettingsRepository.get_settings(session)
        mod_count, queued_count = await PostRepository.get_queue_counts(session)
        
        stmt = select(ProcessedPost.id).where(ProcessedPost.status == 'accumulated')
        acc_result = await session.execute(stmt)
        accumulated_count = len(acc_result.all())
        
        lines = [
            "<b>Текущий статус бота:</b>\n",
            f"• <b>Режим:</b> <code>{settings.mode}</code>",
            f"• <b>Интервал:</b> <code>{format_seconds_readable(settings.interval_min)} - {format_seconds_readable(settings.interval_max)}</code>",
        ]
        
        now = datetime.now(timezone.utc)
        if settings.pause_until and settings.pause_until > now:
            if (settings.pause_until - now).days > 365:
                lines.append("• <b>Пауза:</b> <code>Навсегда</code>")
            else:
                pause_sec = int((settings.pause_until - now).total_seconds())
                lines.append(f"• <b>Пауза до:</b> <code>{settings.pause_until.strftime('%Y-%m-%d %H:%M:%S')} UTC</code> (~{format_seconds_readable(pause_sec)})")
        else:
            lines.append("• <b>Пауза:</b> <code>Активен</code>")
            
        if settings.next_post_time and settings.next_post_time > now:
            delay_sec = int((settings.next_post_time - now).total_seconds())
            lines.append(f"• <b>Следующий пост через:</b> <code>{format_seconds_readable(delay_sec)}</code>")
            
        lines.append("")
        lines.append(f"• <b>На модерации:</b> <code>{mod_count} / 1</code>")
        lines.append(f"• <b>В очереди (auto):</b> <code>{queued_count} / 5</code>")
        lines.append(f"• <b>В корзине (curation):</b> <code>{accumulated_count}</code>")
        
        text = "\n".join(lines)
        return text

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
    from arq.connections import RedisSettings
    
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
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
        await message.reply("Интервал успешно отключен! Посты будут выходить по мере готовности.")
        return
        
    parts = [p.strip() for p in re.split(r'[-\u2013\u2014]', args) if p.strip()]
    try:
        min_delta = parse_time_suffix(parts[0])
        max_delta = parse_time_suffix(parts[1]) if len(parts) > 1 else min_delta
        
        if not min_delta or not max_delta:
            raise ValueError()
            
        interval_min = int(min_delta.total_seconds())
        interval_max = int(max_delta.total_seconds())
        
        if interval_min > interval_max:
            interval_min, interval_max = interval_max, interval_min
            
        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, interval_min=interval_min, interval_max=interval_max)
            
        await message.reply(
            f"<b>Интервал успешно установлен:</b>\n"
            f"от <b>{format_seconds_readable(interval_min)}</b> до <b>{format_seconds_readable(interval_max)}</b>.",
            parse_mode="HTML"
        )
    except Exception:
        await message.reply("Неверный формат. Пример: /interval 20m-50m или /interval 30-60")


@router.message(Command("pause"), IsModeratorFilter())
async def cmd_pause(message: Message, command: CommandObject):
    pause_until = None
    msg_text = "<b>Бот поставлен на ВЕЧНУЮ паузу.</b>\nПарсер отключен. Для возобновления работы отправьте /resume."
    
    if command.args:
        delta = parse_time_suffix(command.args)
        if delta:
            pause_until = datetime.now(timezone.utc) + delta
            pause_sec = int(delta.total_seconds())
            msg_text = f"<b>Бот поставлен на паузу на {format_seconds_readable(pause_sec)}</b> (до {pause_until.strftime('%Y-%m-%d %H:%M:%S')} UTC)."
        else:
            await message.reply("Неверный формат времени. Пример: /pause 8h или /pause 30s")
            return
            
    async with async_session_maker() as session:
        if not pause_until:
            pause_until = datetime.now(timezone.utc) + timedelta(days=36500)
        await SettingsRepository.update_settings(session, pause_until=pause_until)
        
    await message.reply(msg_text, parse_mode="HTML")


@router.message(Command("resume"), IsModeratorFilter())
async def cmd_resume(message: Message):
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, pause_until=None)
    await message.reply("<b>Бот возобновил работу.</b> Пауза снята, парсер активен.", parse_mode="HTML")


@router.message(Command("status"), IsModeratorFilter())
async def cmd_status(message: Message):
    text = await get_status_data()
    await message.reply(text, parse_mode="HTML")


@router.message(Command("clear"), IsModeratorFilter())
async def cmd_clear(message: Message):
    async with async_session_maker() as session:
        stmt = update(ProcessedPost).where(
            ProcessedPost.status.in_(['queued', 'accumulated'])
        ).values(status='failed')
        await session.execute(stmt)
        await session.commit()
    await message.reply("<b>Очередь и корзина полностью очищены.</b>", parse_mode="HTML")


@router.message(Command("help"), IsModeratorFilter())
async def cmd_help(message: Message):
    help_text = (
        "<b>Справка по командам бота-модератора</b>\n\n"
        "<b>Управление режимами:</b>\n"
        "• /mode auto — автоматический режим (1 пост на модерации, до 5 в очереди).\n"
        "• /mode curation — режим кураторства (посты собираются в корзину).\n\n"
        "<b>Управление интервалами:</b>\n"
        "• /interval [мин]-[макс] — случайная задержка. Поддерживает суффиксы: <code>s</code> (сек), <code>m</code> (мин), <code>h</code> (ч), <code>d</code> (д).\n"
        "  <i>Пример: /interval 20m-50m или /interval 30s-1h</i>\n"
        "• /interval [время] — фиксированная задержка.\n"
        "  <i>Пример: /interval 30s</i>\n"
        "• /interval 0 — отключить задержку.\n\n"
        "<b>Пауза и возобновление:</b>\n"
        "• /pause — поставить бота на вечную паузу.\n"
        "• /pause [время] — поставить на паузу на указанное время.\n"
        "  <i>Пример: /pause 8h (на 8 часов) или /pause 30s (на 30 секунд)</i>\n"
        "• /resume — возобновить работу бота (снять паузу).\n\n"
        "<b>Другие команды:</b>\n"
        "• /status — посмотреть настройки, режим и статистику очереди.\n"
        "• /best [время] — найти лучший пост в корзине за указанный период (для curation).\n"
        "  <i>Пример: /best 24h или /best 12h</i>\n"
        "• /clear — полностью очистить очередь и корзину.\n"
    )
    await message.reply(help_text, parse_mode="HTML")


class MediaReplacement(StatesGroup):
    waiting_for_media = State()

class TextReplacement(StatesGroup):
    waiting_for_text = State()


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
    await callback.message.answer(f'Пришлите новое медиа (фото/видео/файл) для поста {post_id}:')
    await state.set_state(MediaReplacement.waiting_for_media)
    await state.update_data(post_id=post_id)
    await callback.message.reply(
        f"Отправьте новое фото, видео или документ для поста <b>#{post_id}</b>. Для отмены отправьте /cancel.",
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
        
    if not media_type:
        await message.reply("Пожалуйста, отправьте медиа (фото/видео/документ).")
        return
        
    import os
    os.makedirs('data/media', exist_ok=True)
    temp_filename = f"media_{post_id}_{int(message.date.timestamp())}"
    
    try:
        file_info = await bot.get_file(file_id)
        file_ext = os.path.splitext(file_info.file_path)[1]
        new_filename = f"{temp_filename}{file_ext}"
        media_path = os.path.join('data/media', new_filename)
        await bot.download_file(file_info.file_path, media_path)
    except Exception as e:
        await message.reply(f"Не удалось сохранить медиа: {e}")
        await state.clear()
        return

    async with async_session_maker() as session:
        post = await PostRepository.atomic_update_media(session, post_id, 'moderating', media_path, media_type)
        if post:
            await send_mod_card_to_chat(bot, message.chat.id, post)
        else:
            await message.reply("Пост уже обработан или не найден.")
            
    await state.clear()

# --- Reply Keyboard Button Handlers ---

@router.message(Command('parse'), IsModeratorFilter())
async def cmd_parse(message: Message):
    from arq.connections import RedisSettings
    from arq import create_pool
    
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.set('force_parse', '10')
        await message.reply("Сигнал на ручной парсинг отправлен. Парсер загружает последние 10 сообщений из каждого канала...")
    except Exception as e:
        await message.reply(f"Ошибка при отправке сигнала парсеру: {e}")
    finally:
        await redis.close()

@router.message(F.text == "Парсить сейчас", IsModeratorFilter())
async def reply_parse_now(message: Message):
    await cmd_parse(message)

@router.message(F.text == "Найти лучший пост", IsModeratorFilter())
async def reply_find_best(message: Message):
    class DummyCommand:
        args = None
    await cmd_best(message, DummyCommand())

@router.message(F.text == "Статус", IsModeratorFilter())
async def reply_status(message: Message):
    await cmd_status(message)


@router.message(F.text == "Помощь", IsModeratorFilter())
async def reply_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "Пауза 8ч", IsModeratorFilter())
async def reply_pause_8h(message: Message):
    pause_until = datetime.now(timezone.utc) + timedelta(hours=8)
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, pause_until=pause_until)
    await message.reply("Бот поставлен на паузу на 8 часов (до " + pause_until.strftime('%Y-%m-%d %H:%M:%S') + " UTC).")


@router.message(F.text == "Возобновить", IsModeratorFilter())
async def reply_resume(message: Message):
    await cmd_resume(message)


@router.message(F.text == "Сбросить интервал", IsModeratorFilter())
async def reply_reset_interval(message: Message):
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, next_post_time=None)
        stmt = select(ProcessedPost.id).where(ProcessedPost.status == 'queued')
        result = await session.execute(stmt)
        queued_ids = result.scalars().all()
        
    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        for q_id in queued_ids:
            await redis.enqueue_job('process_post_task', q_id)
    finally:
        await redis.close()
        
    if queued_ids:
        await message.reply(f"Интервал сброшен! Запущено {len(queued_ids)} постов в обработку.")
    else:
        await message.reply("Интервал сброшен!")


@router.message(F.text == "Очистить очередь", IsModeratorFilter())
async def reply_clear_confirm(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, очистить", callback_data="btn_quick_clear_yes"),
            InlineKeyboardButton(text="Отмена", callback_data="btn_quick_clear_no")
        ]
    ])
    await message.reply("Вы действительно хотите полностью очистить очередь публикации и кураторскую корзину?", reply_markup=keyboard)

@router.message(IsModeratorFilter())
async def handle_manual_post(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state is not None:
        return

    if message.text and message.text.startswith('/'):
        return

    text = message.text or message.caption or ""
    if not text.strip() and not message.photo and not message.video and not message.document:
        await message.reply("Пожалуйста, отправьте текст или медиафайл для рерайта.")
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

    import os
    os.makedirs('data/media', exist_ok=True)
    media_path = None
    temp_filename = f"manual_{int(datetime.now(timezone.utc).timestamp())}"

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
            await message.reply("Не удалось скачать медиафайл. Попробуйте еще раз.")
            return

    import hashlib
    post_hash = hashlib.md5(f"manual_{text}_{datetime.now(timezone.utc).timestamp()}".encode('utf-8')).hexdigest()

    async with async_session_maker() as session:
        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=0,
            message_id=0,
            post_hash=post_hash,
            text=text,
            media_path=media_path,
            media_type=media_type,
            source_link="Ручной пост",
            status='queued'
        )
        await SettingsRepository.update_settings(session, next_post_time=None)

    if not post_id:
        await message.reply("Не удалось создать пост в базе данных.")
        return

    from arq import create_pool
    from arq.connections import RedisSettings
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.enqueue_job('process_post_task', post_id)
        await message.reply(f"Пост принят для ручной обработки (ID: {post_id}). Запускаю ИИ-рерайт...")
    finally:
        await redis.close()
