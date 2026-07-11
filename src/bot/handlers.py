from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, BaseFilter
from src.core.logger import logger
from src.core.config import settings
from src.database.engine import async_session_maker
from src.database.repository import PostRepository

class IsModeratorFilter(BaseFilter):
    async def __call__(self, event) -> bool:
        from aiogram.types import Message, CallbackQuery
        if isinstance(event, Message):
            chat_id = event.chat.id
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
            user_id = event.from_user.id
        else:
            return False
            
        is_admin = user_id in settings.ADMIN_IDS
        is_right_chat = str(chat_id) == str(settings.MODERATOR_CHAT_ID)
        
        if is_right_chat and not is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещен", show_alert=True)
            return False
            
        return is_admin and is_right_chat

router = Router()

@router.callback_query(F.data.startswith("publish_"), IsModeratorFilter())
async def process_publish(callback: CallbackQuery, bot: Bot):
    post_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer("Пост уже обработан или не найден.", show_alert=True)
            return
            
        text_to_publish = post.rewritten_text
        if not text_to_publish:
            await callback.answer("Ошибка: нет текста для публикации.", show_alert=True)
            return

        try:
            # Publish to target channel
            await bot.send_message(
                chat_id=settings.TARGET_CHANNEL_ID,
                text=text_to_publish,
                parse_mode=None  # Or HTML depending on requirements, but usually raw text is fine or we keep formatting
            )
            
            # Update DB
            await PostRepository.update_status(session, post_id, 'published')
            
            # Edit moderator message
            display_text = text_to_publish[:4000]
            new_text = f"✅ <b>Опубликовано</b>\n\n{display_text}"
            await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
            
            await callback.answer("Опубликовано!")
            logger.info(f"[Bot] Пост {post_id} опубликован в канал.")
        except Exception as e:
            logger.error(f"[Bot] Ошибка публикации поста {post_id}: {e}")
            await callback.answer("Ошибка при публикации.", show_alert=True)

@router.callback_query(F.data.startswith("reject_"), IsModeratorFilter())
async def process_reject(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer("Пост уже обработан или не найден.", show_alert=True)
            return
            
        await PostRepository.update_status(session, post_id, 'rejected')
        
        display_text = post.rewritten_text[:4000] if post.rewritten_text else ""
        new_text = f"❌ <b>Отклонено</b>\n\n{display_text}"
        await callback.message.edit_text(text=new_text, reply_markup=None, parse_mode="HTML")
        await callback.answer("Пост отклонен.")
        logger.info(f"[Bot] Пост {post_id} отклонен.")

@router.callback_query(F.data.startswith("edit_"), IsModeratorFilter())
async def process_edit(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[1])
    
    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await callback.answer("Пост уже обработан или не найден.", show_alert=True)
            return
            
        instruction = (
            f"Для редактирования скопируйте текст ниже, внесите правки и отправьте команду:\n"
            f"<code>/edit {post_id} Ваш исправленный текст</code>"
        )
        await callback.message.answer(instruction, parse_mode="HTML")
        await callback.message.answer(post.rewritten_text)
        await callback.answer()

@router.message(Command("edit"), IsModeratorFilter())
async def process_edit_command(message: Message):
    # Command format: /edit <post_id> <new_text>
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Неверный формат команды. Используйте:\n/edit <ID_поста> <Новый текст>")
        return
        
    post_id_str = args[1]
    if not post_id_str.isdigit():
        await message.reply("ID поста должен быть числом.")
        return
        
    post_id = int(post_id_str)
    
    # Use slicing to preserve all formatting and newlines safely
    new_text = message.text[len(f"/edit {post_id} "):].strip()
    
    async with async_session_maker() as session:
        post = await PostRepository.get_post_by_id(session, post_id)
        if not post or post.status != 'moderating':
            await message.reply("Пост не найден или уже не находится на модерации.")
            return
            
        # Update text in DB
        await PostRepository.update_rewritten_text(session, post_id, new_text)
        
        # Send new moderation card
        display_text = new_text[:4000]
        text_to_send = f"<b>Новый пост из источника {post.source_channel_id} (Исправлено)</b>\n\n{display_text}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{post_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{post_id}")
            ],
            [
                InlineKeyboardButton(text="✏️ Править", callback_data=f"edit_{post_id}")
            ]
        ])
        
        await message.answer(text_to_send, reply_markup=keyboard, parse_mode="HTML")
        await message.reply("Текст обновлен! Новая карточка отправлена.")
        logger.info(f"[Bot] Текст поста {post_id} изменен вручную модератором.")
