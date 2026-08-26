import re
from datetime import datetime, timezone, timedelta
from html import escape

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, delete

from src.core.logger import logger
from src.core.config import settings
from src.core.i18n import i18n
from src.core.utils import parse_time_suffix, format_seconds_readable
from src.database.engine import async_session_maker
from src.database.repository import PostRepository, SettingsRepository
from src.database.models import ProcessedPost

from src.bot.filters import IsModeratorFilter
from src.bot.states import PromptState
from src.bot.keyboards import get_main_reply_keyboard, get_main_inline_keyboard


router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in settings.ADMIN_IDS:
        logger.warning(f"Unauthorized user {user_id} tried to use start command.")
        await message.reply(
            i18n.get('start_access_denied', user_id=user_id),
            parse_mode="HTML"
        )
        return

    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
    # Explicit UI language sync (get_settings no longer mutates global i18n)
    i18n.set_language(bot_settings.ui_lang)

    keyboard = get_main_reply_keyboard()
    await message.reply(
        i18n.get('start_welcome'),
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    # Step 1: Select Interface Language
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_lang_ru', lang='ru'), callback_data="set_uilang_ru"),
            InlineKeyboardButton(text=i18n.get('btn_lang_en', lang='en'), callback_data="set_uilang_en")
        ]
    ])
    await message.answer(
        i18n.get('start_select_ui_lang'),
        reply_markup=lang_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_({"set_uilang_ru", "set_uilang_en"}), IsModeratorFilter())
async def process_set_uilang(callback: CallbackQuery):
    chosen_lang = "ru" if callback.data == "set_uilang_ru" else "en"
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, ui_lang=chosen_lang)

    i18n.set_language(chosen_lang)
    await callback.answer(i18n.get('lang_ui_set', lang="Русский" if chosen_lang == "ru" else "English"))

    # Step 2: Select Posts Language (AI)
    post_lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_lang_ru', lang='ru'), callback_data="set_postlang_ru"),
            InlineKeyboardButton(text=i18n.get('btn_lang_en', lang='en'), callback_data="set_postlang_en")
        ]
    ])
    try:
        await callback.message.edit_text(
            i18n.get('start_select_post_lang'),
            reply_markup=post_lang_kb,
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            i18n.get('start_select_post_lang'),
            reply_markup=post_lang_kb,
            parse_mode="HTML"
        )


@router.callback_query(F.data.in_({"set_postlang_ru", "set_postlang_en"}), IsModeratorFilter())
async def process_set_postlang(callback: CallbackQuery):
    chosen_lang = "ru" if callback.data == "set_postlang_ru" else "en"
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, post_lang=chosen_lang)

    await callback.answer(i18n.get('lang_post_set', lang="Русский" if chosen_lang == "ru" else "English"))

    try:
        await callback.message.edit_text(
            i18n.get('lang_setup_complete'),
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            i18n.get('lang_setup_complete'),
            parse_mode="HTML"
        )


@router.message(Command("settings"), IsModeratorFilter())
@router.message(Command("languages"), IsModeratorFilter())
@router.message(Command("lang"), IsModeratorFilter())
@router.callback_query(F.data == "menu_languages", IsModeratorFilter())
async def cmd_settings_languages(event: Message | CallbackQuery):
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)

    text = i18n.get(
        'menu_lang_title',
        ui_lang=(bot_settings.ui_lang or 'ru').upper(),
        post_lang=(bot_settings.post_lang or 'ru').upper()
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get('btn_change_ui_lang'), callback_data="btn_change_ui_lang")],
        [InlineKeyboardButton(text=i18n.get('btn_change_post_lang'), callback_data="btn_change_post_lang")]
    ])

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.reply(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "btn_change_ui_lang", IsModeratorFilter())
async def cb_change_ui_lang(callback: CallbackQuery):
    await callback.answer()
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_lang_ru', lang='ru'), callback_data="set_uilang_ru"),
            InlineKeyboardButton(text=i18n.get('btn_lang_en', lang='en'), callback_data="set_uilang_en")
        ]
    ])
    await callback.message.answer(
        i18n.get('start_select_ui_lang'),
        reply_markup=lang_kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "btn_change_post_lang", IsModeratorFilter())
async def cb_change_post_lang(callback: CallbackQuery):
    await callback.answer()
    post_lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_lang_ru', lang='ru'), callback_data="set_postlang_ru"),
            InlineKeyboardButton(text=i18n.get('btn_lang_en', lang='en'), callback_data="set_postlang_en")
        ]
    ])
    await callback.message.answer(
        i18n.get('start_select_post_lang'),
        reply_markup=post_lang_kb,
        parse_mode="HTML"
    )


# --- AI System Prompt Management ---

@router.message(Command("prompt"), IsModeratorFilter())
@router.message(Command("prompts"), IsModeratorFilter())
@router.callback_query(F.data == "menu_prompt", IsModeratorFilter())
async def cmd_prompt_menu(event: Message | CallbackQuery):
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)

    custom_prompt = getattr(bot_settings, 'custom_prompt', None)
    post_lang = getattr(bot_settings, 'post_lang', 'ru')

    if custom_prompt and custom_prompt.strip():
        status = i18n.get('prompt_status_custom', length=len(custom_prompt.strip()))
        preview_text = custom_prompt.strip()[:250] + ("..." if len(custom_prompt.strip()) > 250 else "")
        preview = i18n.get('prompt_preview_label', text=escape(preview_text))
    else:
        status = i18n.get('prompt_status_default', lang=post_lang.upper())
        preview = ""

    text = i18n.get('prompt_menu_title', status=status, preview=preview)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_set_prompt'), callback_data="prompt_set"),
            InlineKeyboardButton(text=i18n.get('btn_reset_prompt'), callback_data="prompt_reset")
        ],
        [
            InlineKeyboardButton(text=i18n.get('btn_show_prompt'), callback_data="prompt_show")
        ]
    ])

    if isinstance(event, CallbackQuery):
        await event.answer()
        await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.reply(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("set_prompt"), IsModeratorFilter())
@router.message(Command("setprompt"), IsModeratorFilter())
async def cmd_set_prompt(message: Message, command: CommandObject, state: FSMContext):
    if command and command.args and command.args.strip():
        new_prompt = command.args.strip()
        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, custom_prompt=new_prompt)
        await message.reply(
            i18n.get('prompt_updated', length=len(new_prompt)),
            parse_mode="HTML"
        )
    else:
        await state.set_state(PromptState.waiting_for_prompt)
        await message.reply(i18n.get('prompt_send_new'), parse_mode="HTML")


@router.message(Command("reset_prompt"), IsModeratorFilter())
@router.message(Command("resetprompt"), IsModeratorFilter())
async def cmd_reset_prompt(message: Message):
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
        await SettingsRepository.update_settings(session, custom_prompt=None)
        post_lang = getattr(bot_settings, 'post_lang', 'ru')
    await message.reply(i18n.get('prompt_reset_done', lang=post_lang.upper()), parse_mode="HTML")


@router.callback_query(F.data == "prompt_set", IsModeratorFilter())
async def cb_prompt_set(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PromptState.waiting_for_prompt)
    await callback.answer()
    await callback.message.answer(i18n.get('prompt_send_new'), parse_mode="HTML")


@router.callback_query(F.data == "prompt_reset", IsModeratorFilter())
async def cb_prompt_reset(callback: CallbackQuery):
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
        await SettingsRepository.update_settings(session, custom_prompt=None)
        post_lang = getattr(bot_settings, 'post_lang', 'ru')
    await callback.answer(i18n.get('prompt_reset_done', lang=post_lang.upper()), show_alert=True)
    await cmd_prompt_menu(callback)


@router.callback_query(F.data == "prompt_show", IsModeratorFilter())
async def cb_prompt_show(callback: CallbackQuery):
    from src.core.prompts import get_system_prompt
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
    post_lang = getattr(bot_settings, 'post_lang', 'ru')
    custom_prompt = getattr(bot_settings, 'custom_prompt', None)

    prompt_text = get_system_prompt(post_lang, custom_prompt)
    prompt_type = "Custom" if (custom_prompt and custom_prompt.strip()) else f"Default ({post_lang.upper()})"

    header = i18n.get('prompt_full_title', type=prompt_type)
    full_message = f"{header}<code>{escape(prompt_text)}</code>"

    await callback.answer()
    if len(full_message) <= 4000:
        await callback.message.answer(full_message, parse_mode="HTML")
    else:
        for i in range(0, len(prompt_text), 3500):
            chunk = prompt_text[i:i+3500]
            await callback.message.answer(f"<code>{escape(chunk)}</code>", parse_mode="HTML")


@router.message(PromptState.waiting_for_prompt, IsModeratorFilter())
async def process_new_prompt_message(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.reply(i18n.get('prompt_canceled'))
        return

    if not message.text or not message.text.strip():
        await message.reply(i18n.get('prompt_send_new'), parse_mode="HTML")
        return

    new_prompt = message.text.strip()
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, custom_prompt=new_prompt)

    await state.clear()
    await message.reply(
        i18n.get('prompt_updated', length=len(new_prompt)),
        parse_mode="HTML"
    )


@router.message(Command("edit"), IsModeratorFilter())
async def process_edit_command(message: Message, command: CommandObject):
    from src.bot.messaging import send_mod_card_to_chat

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

async def get_status_data():
    async with async_session_maker() as session:
        bot_settings = await SettingsRepository.get_settings(session)
        mod_count, queued_count = await PostRepository.get_queue_counts(session)

        stmt = select(ProcessedPost.id).where(ProcessedPost.status == 'accumulated')
        acc_result = await session.execute(stmt)
        accumulated_count = len(acc_result.all())

        lines = [
            i18n.get('status_title'),
            i18n.get('status_mode', mode=bot_settings.mode),
            i18n.get('status_ui_lang', ui_lang=(bot_settings.ui_lang or 'ru').upper()),
            i18n.get('status_post_lang', post_lang=(bot_settings.post_lang or 'ru').upper()),
            i18n.get('status_interval', min_val=format_seconds_readable(bot_settings.interval_min), max_val=format_seconds_readable(bot_settings.interval_max)),
        ]

        now = datetime.now(timezone.utc)
        if bot_settings.pause_until and bot_settings.pause_until > now:
            if (bot_settings.pause_until - now).days > 365:
                lines.append(i18n.get('status_pause_forever'))
            else:
                pause_sec = int((bot_settings.pause_until - now).total_seconds())
                lines.append(i18n.get('status_pause_until', until=bot_settings.pause_until.strftime('%Y-%m-%d %H:%M:%S'), remaining=format_seconds_readable(pause_sec)))
        else:
            lines.append(i18n.get('status_active'))

        if bot_settings.next_post_time and bot_settings.next_post_time > now:
            delay_sec = int((bot_settings.next_post_time - now).total_seconds())
            lines.append(i18n.get('status_next_post', delay=format_seconds_readable(delay_sec)))

        lines.append("")
        lines.append(i18n.get('status_moderating', count=mod_count))
        lines.append(i18n.get('status_queued', count=queued_count, limit=bot_settings.queue_limit))
        lines.append(i18n.get('status_accumulated', count=accumulated_count))

        return "\n".join(lines)


@router.message(Command("mode"), IsModeratorFilter())
async def cmd_mode(message: Message, command: CommandObject):
    if not command.args or command.args.lower() not in ['auto', 'curation']:
        await message.reply(i18n.get('mode_usage'))
        return

    new_mode = command.args.lower()
    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, mode=new_mode)

    await message.reply(i18n.get('mode_changed', mode=new_mode), parse_mode="HTML")


@router.message(Command("queue"), IsModeratorFilter())
async def cmd_queue(message: Message, command: CommandObject):
    if not command.args:
        async with async_session_maker() as session:
            bot_settings = await SettingsRepository.get_settings(session)
        await message.reply(i18n.get('queue_current', limit=bot_settings.queue_limit), parse_mode="HTML")
        return

    try:
        new_limit = int(command.args.strip())
        if new_limit <= 0 or new_limit > 1000:
            raise ValueError
    except ValueError:
        await message.reply(i18n.get('queue_invalid'))
        return

    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, queue_limit=new_limit)

    await message.reply(i18n.get('queue_changed', limit=new_limit), parse_mode="HTML")


@router.message(Command("best"), IsModeratorFilter())
async def cmd_best(message: Message, command: CommandObject):
    import math

    hours = 12
    if command.args:
        try:
            delta = parse_time_suffix(command.args)
            if delta:
                # Round sub-hour windows up so "/best 45m" doesn't search 0 hours
                hours = max(1, math.ceil(delta.total_seconds() / 3600))
            else:
                hours = int(command.args)
        except ValueError:
            await message.reply(i18n.get('best_invalid_time'))
            return

    from src.core.clients import get_redis_pool

    async with async_session_maker() as session:
        await SettingsRepository.update_settings(session, next_post_time=None)

    redis = await get_redis_pool()
    await redis.enqueue_job('find_best_post_task', hours, requester_chat_id=message.chat.id)
    await message.reply(i18n.get('best_searching', hours=hours))


@router.message(Command("interval"), IsModeratorFilter())
async def cmd_interval(message: Message, command: CommandObject):
    if not command.args:
        await message.reply(i18n.get('interval_usage'))
        return

    args = command.args.strip()
    if args == "0":
        async with async_session_maker() as session:
            # Clear the stale timer so queued posts are not blocked
            await SettingsRepository.update_settings(
                session, interval_min=0, interval_max=0, next_post_time=None
            )
        await message.reply(i18n.get('interval_disabled'))
        return

    parts = [p.strip() for p in re.split(r'[-\u2013\u2014]', args) if p.strip()]
    try:
        min_delta = parse_time_suffix(parts[0])
        max_delta = parse_time_suffix(parts[1]) if len(parts) > 1 else min_delta

        # "is None" (not falsy) so that a zero bound like "/interval 0m-30m" is accepted
        if min_delta is None or max_delta is None:
            raise ValueError()

        interval_min = int(min_delta.total_seconds())
        interval_max = int(max_delta.total_seconds())

        if interval_min > interval_max:
            interval_min, interval_max = interval_max, interval_min

        async with async_session_maker() as session:
            await SettingsRepository.update_settings(session, interval_min=interval_min, interval_max=interval_max)

        await message.reply(
            i18n.get('interval_set', min_val=format_seconds_readable(interval_min), max_val=format_seconds_readable(interval_max)),
            parse_mode="HTML"
        )
    except Exception:
        await message.reply(i18n.get('interval_invalid'))


@router.message(Command("pause"), IsModeratorFilter())
async def cmd_pause(message: Message, command: CommandObject):
    pause_until = None
    msg_text = i18n.get('pause_forever')

    if command.args:
        delta = parse_time_suffix(command.args)
        if delta:
            pause_until = datetime.now(timezone.utc) + delta
            pause_sec = int(delta.total_seconds())
            msg_text = i18n.get('pause_timed', duration=format_seconds_readable(pause_sec), until=pause_until.strftime('%Y-%m-%d %H:%M:%S'))
        else:
            await message.reply(i18n.get('pause_invalid_time'))
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
    await message.reply(i18n.get('resume_done'), parse_mode="HTML")


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
    await message.reply(i18n.get('clear_done'), parse_mode="HTML")


@router.message(Command("clear_db"), IsModeratorFilter())
async def cmd_clear_db(message: Message):
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
    await message.reply(i18n.get('clear_db_done', count=deleted_count), parse_mode="HTML")


@router.message(Command("help"), IsModeratorFilter())
async def cmd_help(message: Message):
    await message.reply(i18n.get('help_text'), parse_mode="HTML")


@router.message(Command('parse'), IsModeratorFilter())
async def cmd_parse(message: Message, command: CommandObject):
    from src.core.clients import get_redis_pool

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

    redis = await get_redis_pool()
    try:
        # format: limit|num_channels|time_offset|requester_chat_id
        await redis.set('force_parse', f"{limit}|{num_channels}|{time_offset}|{message.chat.id}")

        target_str = i18n.get('parse_channels_random', count=num_channels) if num_channels != '0' else i18n.get('parse_channels_all')
        if time_offset:
            await message.reply(i18n.get('parse_signal_time', time=time_offset, channels=target_str))
        else:
            await message.reply(i18n.get('parse_signal_limit', limit=limit, channels=target_str))
    except Exception as e:
        await message.reply(i18n.get('parse_signal_error', error=e))


@router.message(Command("test_ai", "testai", "check_ai"), IsModeratorFilter())
async def cmd_test_ai(message: Message):
    """
    Diagnostic command to verify connection and validity of the AI API key and model in real-time.
    """
    import time
    from html import escape
    from src.core.clients import get_ai_client
    from src.core.ai_notifier import parse_ai_error

    status_msg = await message.reply(
        i18n.get('ai_test_testing', model=escape(settings.AI_MODEL), endpoint=escape(settings.AI_BASE_URL)),
        parse_mode="HTML"
    )

    client = get_ai_client()
    start_time = time.time()

    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[
                {"role": "system", "content": "You are a test ping bot. Respond with exactly one word: 'OK'."},
                {"role": "user", "content": "Ping test."}
            ],
            extra_body=settings.AI_EXTRA_BODY or {},
            timeout=30.0
        )
        latency = round(time.time() - start_time, 2)
        reply_content = response.choices[0].message.content.strip() if response.choices else "OK"

        await status_msg.edit_text(
            i18n.get(
                'ai_test_success',
                model=escape(settings.AI_MODEL),
                response=escape(reply_content),
                latency=latency
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        latency = round(time.time() - start_time, 2)
        cat, reason, detail = parse_ai_error(e)
        clean_detail = escape(detail[:400] + ("..." if len(detail) > 400 else ""))

        error_card = (
            f"🚨 <b>Сбой подключения к AI API</b> ({latency} сек)\n\n"
            f"❌ <b>Причина:</b> {reason}\n"
            f"🤖 <b>Модель:</b> <code>{escape(settings.AI_MODEL)}</code>\n"
            f"🌐 <b>Эндпоинт:</b> <code>{escape(settings.AI_BASE_URL)}</code>\n\n"
            f"📋 <b>Детали ошибки:</b>\n"
            f"<blockquote><code>{clean_detail}</code></blockquote>\n\n"
            f"💡 <b>Решение:</b>\n"
            f"• Проверьте актуальность модели в файле <code>.env</code> (параметр <code>AI_MODEL</code>).\n"
            f"• Проверьте баланс и валидность ключа (параметр <code>AI_API_KEY</code>)."
        )
        await status_msg.edit_text(error_card, parse_mode="HTML")

