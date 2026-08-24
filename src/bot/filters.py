from aiogram.types import CallbackQuery, Message
from aiogram.filters import BaseFilter

from src.core.config import settings
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
            user_id = event.from_user.id
            if event.message is None:
                # Message too old or deleted: Telegram can't show it, but the
                # moderator still deserves feedback instead of silence
                await event.answer(i18n.get('msg_already_processed'), show_alert=True)
                return False
            chat_id = event.message.chat.id
        else:
            return False

        is_admin = user_id in settings.ADMIN_IDS
        is_right_chat = str(chat_id) == str(settings.effective_moderator_chat_id) or str(chat_id) == str(user_id)

        if is_right_chat and not is_admin:
            if isinstance(event, CallbackQuery):
                await event.answer(i18n.get('msg_access_denied'), show_alert=True)
            return False

        return is_admin and is_right_chat
