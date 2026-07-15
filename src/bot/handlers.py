from html import escape
from src.core.utils import format_telegram_html
import os
from aiogram import Router, F, Bot
from aiogram.fsm.state import State, StatesGroup
class MediaReplacement(StatesGroup):
    waiting_for_media = State()

class TextReplacement(StatesGroup):
    waiting_for_text = State()

class AIEditState(StatesGroup):
    waiting_for_instruction = State()



from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, BaseFilter, CommandObject
from src.core.logger import logger
from src.core.config import settings
from src.core.constants import TG_SAFE_MESSAGE_LIMIT, TG_MESSAGE_LIMIT
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from src.database.models import ProcessedPost
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
        is_right_chat = str(chat_id) == str(settings.effective_moderator_chat_id) or str(chat_id) == str(user_id)

        if is_right_chat and not is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer(i18n.get('msg_access_denied'), show_alert=True)
            return False

        return is_admin and is_right_chat


def get_main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="\U0001f4cb Модерация"),
                KeyboardButton(text="\U0001f4ca Статус")
            ],
            [
                KeyboardButton(text="\U0001f504 Парсить сейчас"),
                KeyboardButton(text="\u2b50 Найти лучший пост")
            ],
            [
                KeyboardButton(text="\u23f8 Пауза 8ч"),
                KeyboardButton(text="\u25b6 Возобновить")
            ],
            [
                KeyboardButton(text="🗑 Очистить все"),
                KeyboardButton(text="🗄 Очистить БД")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def get_main_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Модерация", callback_data="menu_moderation"),
            InlineKeyboardButton(text="🔄 Обновить статус", callback_data="menu_status")
        ],
        [
            InlineKeyboardButton(text="⚡️ Парсить сейчас", callback_data="menu_parse"),
            InlineKeyboardButton(text="⭐️ Найти лучший пост", callback_data="menu_best")
        ],
        [
            InlineKeyboardButton(text="⏸ Пауза 8ч", callback_data="menu_pause_8h"),
            InlineKeyboardButton(text="▶️ Возобновить", callback_data="menu_resume")
        ],
        [
            InlineKeyboardButton(text="🗑 Очистить все", callback_data="menu_clear_all"),
            InlineKeyboardButton(text="🗄 Очистить БД", callback_data="menu_clear_db")
        ]
    ])


def _parse_post_id(callback_data: str) -> int | None:
    """Safely extracts post ID from callback_data like 'publish_123' or 'change_media_123'."""
    parts = callback_data.rsplit("_", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        return None
    return int(parts[1])


async def send_notification_to_all(bot: Bot, text: str, requester_chat_id: int | None = None):
    """Sends a text message to the requester, or both the main moderation channel and the first admin PM if not specified."""
    if requester_chat_id:
        chat_ids = [str(requester_chat_id)]
    else:
        chat_ids = [settings.effective_moderator_chat_id]
        if settings.ADMIN_IDS and str(settings.ADMIN_IDS[0]) != str(settings.effective_moderator_chat_id):
            chat_ids.append(str(settings.ADMIN_IDS[0]))
    
    for cid in set(chat_ids):
        if not cid:
            continue
        try:
            await bot.send_message(chat_id=cid, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"[Bot] Error sending notification to {cid}: {e}")


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
            published_with_media = False
            if post.media_path and post.media_type:
                abs_path = os.path.abspath(post.media_path)
                if os.path.exists(abs_path):
                    media_file = FSInputFile(abs_path)
                    formatted_pub_text = format_telegram_html(text_to_publish)
                    if post.media_type == 'photo':
                        await bot.send_photo(chat_id=settings.TARGET_CHANNEL_ID, photo=media_file, caption=formatted_pub_text, parse_mode="HTML")
                    elif post.media_type == 'video':
                        await bot.send_video(chat_id=settings.TARGET_CHANNEL_ID, video=media_file, caption=formatted_pub_text, parse_mode="HTML")
                    else:
                        await bot.send_document(chat_id=settings.TARGET_CHANNEL_ID, document=media_file, caption=formatted_pub_text, parse_mode="HTML")
                    published_with_media = True
                else:
                    logger.warning(f"[Bot] Media file not found: {abs_path}. Publishing as text.")
            if not published_with_media:
                await bot.send_message(chat_id=settings.TARGET_CHANNEL_ID, text=format_telegram_html(text_to_publish), parse_mode="HTML")

            # Edit moderator message — escape user content before embedding in HTML
            action_by = callback.from_user.username or callback.from_user.full_name
            display_text = format_telegram_html(text_to_publish[:TG_SAFE_MESSAGE_LIMIT])
            new_text = f"{i18n.get('msg_published')}\n👤 Действие от: {action_by}\n\n{display_text}"
            
            if callback.message.photo or callback.message.video or callback.message.document:
                await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")

            _cleanup_media(post.media_path, "публикации")

            await _apply_interval_after_moderation(session)

            await callback.answer(i18n.get('msg_published_alert'))

            logger.info(f"[Bot] Пост {post_id} опубликован в канал.")
        except Exception as e:
            # Revert status back to moderating so we don't block the post permanently
            async with async_session_maker() as rollback_session:
                await PostRepository.update_status(rollback_session, post_id, 'moderating')
            logger.error(f"[Bot] Ошибка публикации поста {post_id}: {e}")
            await callback.answer(f"❌ Ошибка публикации: {e}", show_alert=True)

async def _apply_interval_after_moderation(session):
    from src.database.repository import SettingsRepository
    import random
    from datetime import datetime, timezone, timedelta
    
    settings = await SettingsRepository.get_settings(session)
    if settings.interval_max > 0:
        delay = random.randint(settings.interval_min, settings.interval_max)
        next_time = datetime.now(timezone.utc) + timedelta(seconds=delay)
        await SettingsRepository.update_settings(session, next_post_time=next_time)
        logger.info(f"[Bot] Интервал запущен: следующий пост будет через {delay} секунд.")
    else:
        await SettingsRepository.update_settings(session, next_post_time=None)

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

        action_by = callback.from_user.username or callback.from_user.full_name
        display_text = format_telegram_html((post.rewritten_text or "")[:TG_MESSAGE_LIMIT])
        new_text = f"{i18n.get('msg_rejected')}\n👤 Действие от: {action_by}\n\n{display_text}"
        
        if callback.message.photo or callback.message.video or callback.message.document:
            await callback.message.edit_caption(caption=new_text, reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
            
        _cleanup_media(post.media_path, "отклонения")

        await _apply_interval_after_moderation(session)

        await callback.answer(i18n.get('msg_rejected_alert'))
        logger.info(f"[Bot] Пост {post_id} отклонен.")


async def send_mod_card_to_chat(bot: Bot, chat_id: int, post: ProcessedPost):
    display_text = format_telegram_html((post.rewritten_text or post.text)[:TG_SAFE_MESSAGE_LIMIT])
    
    text_to_send = display_text
        
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{post.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{post.id}")
        ],
        [
            InlineKeyboardButton(text="📝 Текст", callback_data=f"edit_{post.id}"),
            InlineKeyboardButton(text="🖼 Медиа", callback_data=f"change_media_{post.id}")
        ],
        [
            InlineKeyboardButton(text="✨ ИИ Редактор", callback_data=f"ai_edit_{post.id}")
        ]
    ])

    from src.core.config import settings
    chat_ids_to_send = [chat_id]
    
    # Если chat_id (обычно это группа) отличается от админского ID (лички), отправляем в оба
    if settings.ADMIN_IDS and str(settings.ADMIN_IDS[0]) != str(chat_id):
        chat_ids_to_send.append(settings.ADMIN_IDS[0])

    for target_chat_id in set(chat_ids_to_send):
        sent = False
        if post.media_path and post.media_type:
            import os
            abs_media_path = os.path.abspath(post.media_path)
            if os.path.exists(abs_media_path):
                try:
                    media_file = FSInputFile(abs_media_path)
                    if post.media_type == 'photo':
                        await bot.send_photo(chat_id=target_chat_id, photo=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
                    elif post.media_type == 'video':
                        await bot.send_video(chat_id=target_chat_id, video=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
                    else:
                        await bot.send_document(chat_id=target_chat_id, document=media_file, caption=text_to_send, reply_markup=keyboard, parse_mode="HTML")
                    sent = True
                except Exception as e:
                    logger.error(f"[Bot] Error sending media to {target_chat_id}: {e}")

        if not sent:
            try:
                await bot.send_message(chat_id=target_chat_id, text=text_to_send, reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                if "group chat was upgraded to a supergroup chat" in str(e):
                    logger.error(f"[Bot] effective_moderator_chat_id is outdated due to supergroup migration. Please update .env!")
                logger.error(f"[Bot] Error sending message to {target_chat_id}: {e}")

    # Отправляем ссылки и источник отдельным СМС в конце
    import re
    extra_links = []
    if post.text:
        all_urls = re.findall(r'https?://[^\s>]+', post.text)
        for url in all_urls:
            url = url.rstrip('.,);:!?')
            if "t.me/" in url:
                continue
            if url not in extra_links:
                extra_links.append(url)

    extra_parts = []
    if extra_links:
        links_formatted = "\n".join([f"• {l}" for l in extra_links])
        extra_parts.append(f"<b>Дополнительные ссылки:</b>\n{links_formatted}")
    if post.source_link:
        extra_parts.append(f"<b>Источник:</b> <a href='{post.source_link}'>Перейти к оригиналу</a>")

    if extra_parts:
        extra_text = "\n\n".join(extra_parts)
        for target_chat_id in set(chat_ids_to_send):
            try:
                await bot.send_message(chat_id=target_chat_id, text=extra_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"[Bot] Error sending extra links to {target_chat_id}: {e}")

@router.message(F.text == "\U0001f4cb Модерация", IsModeratorFilter())
async def reply_moderation(message: Message, bot: Bot):
    from sqlalchemy import select, func
    from src.database.engine import async_session_maker
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
                # Atomically update to ai_processing
                post_locked = await PostRepository.atomic_status_update(session, next_post.id, next_post.status, 'ai_processing')
                if post_locked:
                    progress_msg = await message.reply("🔄 Извлекаю следующий пост из очереди и запускаю ИИ-рерайт...")
                    
                    from openai import AsyncOpenAI
                    from src.worker.tasks import _call_ai_with_retry
                    ai_client = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
                    
                    # Release session lock during network call
                    await session.commit()
                    
                    rewritten = await _call_ai_with_retry(ai_client, post_locked.text, post_locked.id)
                    if rewritten:
                        async with async_session_maker() as new_session:
                            await PostRepository.update_post_ready_for_moderation(new_session, post_locked.id, rewritten)
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
                        await progress_msg.edit_text("❌ Не удалось переписать пост с помощью ИИ.")
                        return
                else:
                    # Locked by another process
                    await message.reply("Пост уже обрабатывается. Пожалуйста, нажмите «Модерация» еще раз через пару секунд.")
                    return
            else:
                # No posts at all
                await message.reply("Очередь модерации и входящих постов пуста.")
                return

        # Count total moderating posts
        count_stmt = select(func.count()).select_from(ProcessedPost).where(ProcessedPost.status == 'moderating')
        total = (await session.execute(count_stmt)).scalar() or 0
        
    await message.reply(f"На модерации осталось постов: {total}")
    await send_mod_card_to_chat(bot, message.chat.id, post)


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

        # Send new moderation card
        await send_mod_card_to_chat(message.bot, message.chat.id, post)
            
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
        lines.append(f"• <b>В очереди (auto):</b> <code>{queued_count} / {settings.queue_limit}</code>")
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


@router.message(Command("queue"), IsModeratorFilter())
async def cmd_queue(message: Message, command: CommandObject):
    if not command.args:
        async with async_session_maker() as session:
            settings = await SettingsRepository.get_settings(session)
        await message.reply(f"Текущий лимит очереди публикации: <b>{settings.queue_limit}</b> постов.\n\nИспользование: <code>/queue [число]</code> (например: /queue 20).")
        return

    try:
        new_limit = int(command.args.strip())
        if new_limit <= 0 or new_limit > 1000:
            raise ValueError
    except ValueError:
        await message.reply("Пожалуйста, укажите корректное число от 1 до 1000.")
        return

    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, queue_limit=new_limit)
        
    await message.reply(f"Лимит очереди публикации успешно изменен на: <b>{new_limit}</b> постов.", parse_mode="HTML")


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
    
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, next_post_time=None)
        
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.enqueue_job('find_best_post_task', hours, requester_chat_id=message.chat.id)
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
    await message.reply(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")


@router.message(Command("clear"), IsModeratorFilter())
async def cmd_clear(message: Message):
    async with async_session_maker() as session:
        stmt = update(ProcessedPost).where(
            ProcessedPost.status.in_(['queued', 'accumulated', 'moderating', 'ai_processing'])
        ).values(status='failed')
        await session.execute(stmt)
        await session.commit()
    await message.reply("<b>Очередь публикации, модерация и кураторская корзина полностью очищены.</b>", parse_mode="HTML")


@router.message(Command("clear_db"), IsModeratorFilter())
async def cmd_clear_db(message: Message):
    async with async_session_maker() as session:
        stmt = delete(ProcessedPost)
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount
    await message.reply(f"<b>База данных полностью очищена.</b> Удалено записей: {deleted_count}.", parse_mode="HTML")


@router.message(Command("help"), IsModeratorFilter())
async def cmd_help(message: Message):
    help_text = (
        "<b>Справка по командам бота-модератора</b>\n\n"
        "<b>Интерактивные кнопки меню:</b>\n"
        "- Модерация — показать один старейший пост, ожидающий проверки.\n"
        "- Парсить сейчас — принудительно загрузить последние 10 сообщений из каналов.\n"
        "- Найти лучший пост — загрузить посты, сбросить интервал и выбрать ТОП-6 (1 на модерацию, 5 в очередь).\n"
        "- Статус — настройки, режим работы, текущая очередь и задержки.\n"
        "- Возобновить / Пауза 8ч / Очистить queue.\n\n"
        "<b>Управление режимами:</b>\n"
        "- /mode auto — автоматический режим (1 пост на модерации, остальные в очереди).\n"
        "- /mode curation — режим кураторства (все посты собираются в корзину без рерайта).\n\n"
        "<b>Управление интервалами:</b>\n"
        "- /interval [мин]-[макс] — случайная задержка. Поддерживает суффиксы: s (сек), m (мин), h (ч), d (д).\n"
        "  Пример: /interval 20m-50m или /interval 30s-1h\n"
        "- /interval [время] — фиксированная задержка. Пример: /interval 30s\n"
        "- /interval 0 — отключить задержку.\n\n"
        "<b>Пауза и возобновление:</b>\n"
        "- /pause — поставить бота на вечную паузу.\n"
        "- /pause [время] — поставить на паузу на указанное время. Пример: /pause 8h\n"
        "- /resume — возобновить работу бота (снять паузу).\n\n"
        "<b>Другие команды:</b>\n"
        "- /status — посмотреть настройки, режим и статистику.\n"
        "- /best [время] — принудительно запустить парсер и выбрать ТОП-6 лучших постов за период.\n"
        "  Пример: /best 24h или /best 12h\n"
        "- /parse [кол-во или время],[кол-во каналов] — ручной парсинг.\n"
        "  Пример: /parse 24h,5 (парсинг постов за 24ч из 5 случайных каналов)\n"
        "  Пример: /parse 10,2 (парсинг последних 10 постов из 2 случайных каналов)\n"
        "  Пример: /parse 5 (парсинг 5 последних постов со всех каналов)\n"
        "- /clear — полностью очистить очередь публикации и корзину.\n"
        "- /clear_db — полностью очистить базу данных постов.\n"
        "- /queue [лимит] — изменить максимальный размер очереди (по умолчанию 5, например: /queue 20).\n"
    )
    await message.reply(help_text, parse_mode="HTML")


async def ai_custom_edit(text: str, instruction: str) -> str | None:
    """
    Calls OpenAI to rewrite the text based on custom user instruction.
    """
    from openai import AsyncOpenAI
    from src.core.prompts import SYSTEM_PROMPT_REWRITE
    
    client = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_REWRITE},
        {"role": "user", "content": text},
        {"role": "user", "content": f"Сделай следующее с текстом поста: {instruction}. Формат и стиль (заголовок жирным, жирные ключевые слова) сохрани."}
    ]
    
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=messages,
            extra_body=settings.AI_EXTRA_BODY or {}
        )
        return response.choices[0].message.content.strip()
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
        f"Напишите, что ИИ должен сделать с текстом поста <b>#{post_id}</b> (например: <i>'сделай короче'</i>, <i>'добавь больше деталей'</i>, <i>'перепиши в шутливом тоне'</i>).\n\nДля отмены отправьте /cancel.",
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
        await message.reply("Пожалуйста, отправьте текстовую инструкцию.")
        return
        
    if instruction.strip() == "/cancel":
        await state.clear()
        await message.reply("Корректировка отменена.")
        return
        
    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await message.reply("Пост уже обработан или не найден.")
            await state.clear()
            return

    progress_msg = await message.reply("⏳ <b>Нейросеть правит пост по вашему запросу...</b>", parse_mode="HTML")
    
    # Call AI
    new_text = await ai_custom_edit(post.text, instruction)
    
    if not new_text:
        await progress_msg.edit_text("❌ Не удалось изменить пост с помощью ИИ. Попробуйте еще раз.")
        await state.clear()
        return

    # Update database
    async with async_session_maker() as session:
        await PostRepository.atomic_edit_text(session, post_id, 'moderating', new_text)

    await progress_msg.delete()
    await state.clear()

    def get_keyboard(p_id):
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{p_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{p_id}")
            ],
            [
                InlineKeyboardButton(text="📝 Текст", callback_data=f"edit_{p_id}"),
                InlineKeyboardButton(text="🖼 Медиа", callback_data=f"change_media_{p_id}")
            ],
            [
                InlineKeyboardButton(text="✨ ИИ Редактор", callback_data=f"ai_edit_{p_id}")
            ]
        ])

    display_text = format_telegram_html(new_text[:TG_SAFE_MESSAGE_LIMIT])
    
    try:
        if post.media_path and post.media_type:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=mod_card_message_id,
                caption=display_text,
                reply_markup=get_keyboard(post_id),
                parse_mode="HTML"
            )
        else:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=mod_card_message_id,
                text=display_text,
                reply_markup=get_keyboard(post_id),
                parse_mode="HTML"
            )
        await message.reply("✨ Текст поста успешно обновлен нейросетью!")
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
async def cmd_parse(message: Message, command: CommandObject):
    from arq.connections import RedisSettings
    from arq import create_pool
    
    limit = '5'
    num_channels = '0'
    time_offset = ''

    if command.args:
        args = command.args.replace(' ', ',').split(',')
        args = [a for a in args if a]
        if args:
            # First arg can be time like 24h or number like 5
            first = args[0].strip()
            if first.isdigit():
                limit = first
            else:
                time_offset = first
        if len(args) >= 2:
            second = args[1].strip()
            if second.isdigit():
                num_channels = second

    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        # format: limit|num_channels|time_offset|requester_chat_id
        await redis.set('force_parse', f"{limit}|{num_channels}|{time_offset}|{message.chat.id}")
        
        target_str = f"{num_channels} случайных каналов" if num_channels != '0' else "всех каналов"
        if time_offset:
            await message.reply(f"Сигнал отправлен. Парсер загружает сообщения за последние {time_offset} из {target_str}...")
        else:
            await message.reply(f"Сигнал отправлен. Парсер загружает последние {limit} сообщений из {target_str}...")
    except Exception as e:
        await message.reply(f"Ошибка при отправке сигнала парсеру: {e}")
    finally:
        await redis.close()

@router.message(F.text == "\U0001f504 Парсить сейчас", IsModeratorFilter())
async def reply_parse_now(message: Message):
    class DummyCommand:
        args = "5 3"
    await cmd_parse(message, DummyCommand())

@router.message(F.text == "\u2b50 Найти лучший пост", IsModeratorFilter())
async def reply_find_best(message: Message):
    class DummyCommand:
        args = None
    await cmd_best(message, DummyCommand())

@router.message(F.text == "\U0001f4ca Статус", IsModeratorFilter())
async def reply_status(message: Message):
    await cmd_status(message)


@router.message(F.text == "Помощь", IsModeratorFilter())
async def reply_help(message: Message):
    await cmd_help(message)


@router.message(F.text == "\u23f8 Пауза 8ч", IsModeratorFilter())
async def reply_pause_8h(message: Message):
    pause_until = datetime.now(timezone.utc) + timedelta(hours=8)
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, pause_until=pause_until)
    await message.reply("Бот поставлен на паузу на 8 часов (до " + pause_until.strftime('%Y-%m-%d %H:%M:%S') + " UTC).")


@router.message(F.text == "\u25b6 Возобновить", IsModeratorFilter())
async def reply_resume(message: Message):
    await cmd_resume(message)


@router.message(F.text.in_({"Очистить все", "🗑 Очистить все"}), IsModeratorFilter())
async def reply_clear_confirm(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, очистить", callback_data="btn_quick_clear_yes"),
            InlineKeyboardButton(text="Отмена", callback_data="btn_quick_clear_no")
        ]
    ])
    await message.reply("Вы действительно хотите полностью очистить очередь публикации, модерацию и кураторскую корзину?", reply_markup=keyboard)

@router.message(F.text.in_({"Очистить БД", "🗄 Очистить БД"}), IsModeratorFilter())
async def reply_clear_db_confirm(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да, очистить БД", callback_data="btn_db_clear_yes"),
            InlineKeyboardButton(text="Отмена", callback_data="btn_db_clear_no")
        ]
    ])
    await message.reply("Вы действительно хотите полностью очистить БАЗУ ДАННЫХ постов? Это действие удалит всю историю постов.", reply_markup=keyboard)

@router.callback_query(F.data == "btn_quick_clear_yes", IsModeratorFilter())
async def cb_quick_clear_yes(callback: CallbackQuery):
    async with async_session_maker() as session:
        stmt = update(ProcessedPost).where(
            ProcessedPost.status.in_(['queued', 'accumulated', 'moderating', 'ai_processing'])
        ).values(status='failed')
        await session.execute(stmt)
        await session.commit()
    await callback.message.edit_text("<b>Очередь публикации, модерация и кураторская корзина полностью очищены.</b>", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "btn_db_clear_yes", IsModeratorFilter())
async def cb_db_clear_yes(callback: CallbackQuery):
    async with async_session_maker() as session:
        stmt = delete(ProcessedPost)
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount
    await callback.message.edit_text(f"<b>База данных полностью очищена.</b> Удалено записей: {deleted_count}.", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "btn_quick_clear_no", IsModeratorFilter())
async def cb_quick_clear_no(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Очистка отменена")

@router.callback_query(F.data == "btn_db_clear_no", IsModeratorFilter())
async def cb_db_clear_no(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@router.message(IsModeratorFilter())
async def handle_manual_post(message: Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state is not None:
        return

    if message.text and message.text.startswith('/'):
        return

    text = message.text or message.caption or ""
    if not text:
        # Check if there is a caption
        if message.caption:
            text = message.caption
        else:
            await message.reply("Пожалуйста, отправьте текст или медиа с подписью.")
            return

    if len(text.strip()) < 5 and not message.photo and not message.video and not message.document:
        await message.reply("⚠️ Текст слишком короткий. Отправьте нормальный текст для рерайта (минимум 5 символов), чтобы избежать выдумок ИИ.")
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

    import random
    import hashlib
    dummy_message_id = random.randint(1, 1000000000)
    post_hash = hashlib.md5(f"manual_{text}_{datetime.now(timezone.utc).timestamp()}_{dummy_message_id}".encode('utf-8')).hexdigest()

    async with async_session_maker() as session:
        post_id = await PostRepository.process_new_post(
            session=session,
            channel_id=0,
            message_id=dummy_message_id,
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


# --- Status Dashboard Callbacks ---

@router.callback_query(F.data == "menu_status", IsModeratorFilter())
async def cb_menu_status(callback: CallbackQuery):
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Статус обновлен")

@router.callback_query(F.data == "menu_moderation", IsModeratorFilter())
async def cb_menu_moderation(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await reply_moderation(callback.message, bot)

@router.callback_query(F.data == "menu_parse", IsModeratorFilter())
async def cb_menu_parse(callback: CallbackQuery):
    class DummyCommand:
        args = "5 3"
    await callback.answer("Запускаю парсинг...")
    await cmd_parse(callback.message, DummyCommand())

@router.callback_query(F.data == "menu_best", IsModeratorFilter())
async def cb_menu_best(callback: CallbackQuery):
    class DummyCommand:
        args = None
    await callback.answer("Выбираю лучший пост...")
    await cmd_best(callback.message, DummyCommand())

@router.callback_query(F.data == "menu_pause_8h", IsModeratorFilter())
async def cb_menu_pause_8h(callback: CallbackQuery):
    await callback.answer("Пауза на 8 часов")
    await reply_pause_8h(callback.message)
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "menu_resume", IsModeratorFilter())
async def cb_menu_resume(callback: CallbackQuery):
    await callback.answer("Бот возобновил работу")
    await reply_resume(callback.message)
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "menu_clear_all", IsModeratorFilter())
async def cb_menu_clear_all(callback: CallbackQuery):
    await callback.answer("Очистка очереди...")
    await cmd_clear(callback.message)

@router.callback_query(F.data == "menu_clear_db", IsModeratorFilter())
async def cb_menu_clear_db(callback: CallbackQuery):
    await callback.answer("Очистка базы данных...")
    await reply_clear_db_confirm(callback.message)
