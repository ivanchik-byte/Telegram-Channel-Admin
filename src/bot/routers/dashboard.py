"""Reply-keyboard shortcuts, destructive-action confirmations and the
status dashboard menu callbacks. Registered after the command routers and
BEFORE the manual-post catch-all.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, update, delete

from src.core.i18n import i18n
from src.database.engine import async_session_maker
from src.database.repository import SettingsRepository
from src.database.models import ProcessedPost

from src.bot.filters import IsModeratorFilter
from src.bot.keyboards import kb_variants, get_main_inline_keyboard
from src.bot.routers.setup_admin import (
    cmd_parse,
    cmd_best,
    cmd_status,
    cmd_help,
    cmd_resume,
    cmd_clear,
    get_status_data,
)


router = Router()


@dataclass
class DummyCommand:
    """Stands in for CommandObject when keyboard buttons trigger command handlers."""
    args: str | None = None


@router.message(F.text.in_(kb_variants('kb_parse_now')), IsModeratorFilter())
async def reply_parse_now(message: Message):
    await cmd_parse(message, DummyCommand(args="5 3"))


@router.message(F.text.in_(kb_variants('kb_find_best')), IsModeratorFilter())
async def reply_find_best(message: Message):
    await cmd_best(message, DummyCommand(args=None))


@router.message(F.text.in_(kb_variants('kb_status')), IsModeratorFilter())
async def reply_status(message: Message):
    await cmd_status(message)


@router.message(F.text.in_({"Помощь", "Help"}), IsModeratorFilter())
async def reply_help(message: Message):
    await cmd_help(message)


@router.message(F.text.in_(kb_variants('kb_pause_8h')), IsModeratorFilter())
async def reply_pause_8h(message: Message):
    pause_until = datetime.now(timezone.utc) + timedelta(hours=8)
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, pause_until=pause_until)
    await message.reply(i18n.get('pause_8h_done', until=pause_until.strftime('%Y-%m-%d %H:%M:%S')))


@router.message(F.text.in_(kb_variants('kb_resume')), IsModeratorFilter())
async def reply_resume(message: Message):
    await cmd_resume(message)


@router.message(F.text.in_(kb_variants('kb_clear_all')), IsModeratorFilter())
async def reply_clear_confirm(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('clear_confirm_yes'), callback_data="btn_quick_clear_yes"),
            InlineKeyboardButton(text=i18n.get('clear_confirm_no'), callback_data="btn_quick_clear_no")
        ]
    ])
    await message.reply(i18n.get('clear_confirm'), reply_markup=keyboard)


@router.message(F.text.in_(kb_variants('kb_clear_db')), IsModeratorFilter())
async def reply_clear_db_confirm(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('clear_db_confirm_yes'), callback_data="btn_db_clear_yes"),
            InlineKeyboardButton(text=i18n.get('clear_db_confirm_no'), callback_data="btn_db_clear_no")
        ]
    ])
    await message.reply(i18n.get('clear_db_confirm'), reply_markup=keyboard)


@router.callback_query(F.data == "btn_quick_clear_yes", IsModeratorFilter())
async def cb_quick_clear_yes(callback: CallbackQuery):
    async with async_session_maker() as session:
        stmt = update(ProcessedPost).where(
            ProcessedPost.status.in_(['queued', 'accumulated', 'moderating', 'ai_processing'])
        ).values(status='failed')
        await session.execute(stmt)
        await session.commit()
    await callback.message.edit_text(i18n.get('clear_done'), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "btn_db_clear_yes", IsModeratorFilter())
async def cb_db_clear_yes(callback: CallbackQuery):
    from src.core.utils import delete_media_file
    async with async_session_maker() as session:
        # Remove media files before dropping the rows
        all_posts = list((await session.execute(select(ProcessedPost))).scalars().all())
        for old_post in all_posts:
            delete_media_file(old_post.media_path)
        stmt = delete(ProcessedPost)
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount
    await callback.message.edit_text(i18n.get('clear_db_done', count=deleted_count), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "btn_quick_clear_no", IsModeratorFilter())
async def cb_quick_clear_no(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer(i18n.get('clear_cancelled'))


@router.callback_query(F.data == "btn_db_clear_no", IsModeratorFilter())
async def cb_db_clear_no(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer(i18n.get('clear_db_cancelled'))


# --- Status Dashboard Callbacks ---

@router.callback_query(F.data == "menu_status", IsModeratorFilter())
async def cb_menu_status(callback: CallbackQuery):
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer(i18n.get('status_updated'))


@router.callback_query(F.data == "menu_moderation", IsModeratorFilter())
async def cb_menu_moderation(callback: CallbackQuery, bot):
    from src.bot.routers.moderation import reply_moderation
    await callback.answer()
    await reply_moderation(callback.message, bot)


@router.callback_query(F.data == "menu_parse", IsModeratorFilter())
async def cb_menu_parse(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_launching_parse'))
    await cmd_parse(callback.message, DummyCommand(args="5 3"))


@router.callback_query(F.data == "menu_best", IsModeratorFilter())
async def cb_menu_best(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_selecting_best'))
    await cmd_best(callback.message, DummyCommand(args=None))


@router.callback_query(F.data == "menu_pause_8h", IsModeratorFilter())
async def cb_menu_pause_8h(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_pause_8h'))
    await reply_pause_8h(callback.message)
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "menu_resume", IsModeratorFilter())
async def cb_menu_resume(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_resumed'))
    await reply_resume(callback.message)
    text = await get_status_data()
    try:
        await callback.message.edit_text(text, reply_markup=get_main_inline_keyboard(), parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "menu_clear_all", IsModeratorFilter())
async def cb_menu_clear_all(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_clearing_queue'))
    await cmd_clear(callback.message)


@router.callback_query(F.data == "menu_clear_db", IsModeratorFilter())
async def cb_menu_clear_db(callback: CallbackQuery):
    await callback.answer(i18n.get('cb_clearing_db'))
    await reply_clear_db_confirm(callback.message)
