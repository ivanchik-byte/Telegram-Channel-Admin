from html import escape
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
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
            await bot.send_message(
                chat_id=settings.TARGET_CHANNEL_ID,
                text=text_to_publish,
                parse_mode=None
            )

            # Edit moderator message — escape user content before embedding in HTML
            display_text = escape(text_to_publish[:TG_SAFE_MESSAGE_LIMIT])
            new_text = f"{i18n.get('msg_published')}\n\n{display_text}"
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")

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
        await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
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

        await message.answer(text_to_send, reply_markup=keyboard, parse_mode="HTML")
        await message.reply(i18n.get('msg_edit_success'))
        logger.info(f"[Bot] Текст поста {post_id} изменен вручную модератором.")
