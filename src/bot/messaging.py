"""Outbound messaging helpers: media with captions, long messages,
moderation cards and admin notifications.

This module has no aiogram Router — it is shared by both the bot process
and the arq worker (which sends moderation cards from tasks).

HTML contract: all public senders accept RAW (unformatted) text and format
each split chunk with format_telegram_html() themselves. Formatting the whole
text first and splitting afterwards would cut tags at chunk boundaries.
"""
import os
import re
from html import escape

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

from src.core.logger import logger
from src.core.config import settings
from src.core.constants import TG_SAFE_MESSAGE_LIMIT, TG_CAPTION_LIMIT
from src.core.utils import format_telegram_html, split_message_text, strip_html
from src.core.i18n import i18n

# Split margin: formatting adds tag characters (<b>, <a href=...>), so raw
# chunks are kept below TG_MESSAGE_LIMIT to keep formatted chunks within it.
TG_HTML_SPLIT_LIMIT = 3600


def build_mod_card_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Single source of truth for moderation-card buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=i18n.get('btn_publish'), callback_data=f"publish_{post_id}"),
            InlineKeyboardButton(text=i18n.get('btn_reject'), callback_data=f"reject_{post_id}")
        ],
        [
            InlineKeyboardButton(text=i18n.get('btn_edit'), callback_data=f"edit_{post_id}"),
            InlineKeyboardButton(text=i18n.get('btn_change_media'), callback_data=f"change_media_{post_id}")
        ],
        [
            InlineKeyboardButton(text=i18n.get('btn_ai_edit'), callback_data=f"ai_edit_{post_id}")
        ]
    ])


async def _send_chunk(bot: Bot, chat_id: int, raw_chunk: str, reply_markup=None):
    """Sends one raw chunk as HTML; falls back to plain text on parse errors."""
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=format_telegram_html(raw_chunk),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"[Bot] HTML chunk failed ({e}), falling back to plain text")
        return await bot.send_message(
            chat_id=chat_id,
            text=strip_html(raw_chunk)[:4096],
            disable_web_page_preview=True,
        )


async def send_long_message(bot: Bot, chat_id: int, raw_text: str, reply_markup=None):
    """Sends raw text of any length: splits first, formats each chunk after."""
    chunks = split_message_text(raw_text, limit=TG_HTML_SPLIT_LIMIT)
    last_msg = None
    for i, chunk in enumerate(chunks):
        # Buttons only make sense on the last chunk
        last_msg = await _send_chunk(
            bot, chat_id, chunk,
            reply_markup=reply_markup if i == len(chunks) - 1 else None,
        )
    return last_msg


async def send_media_with_caption(bot: Bot, chat_id: int, media_type: str,
                                  media_file, raw_text: str, **extra):
    """Send media with a caption built from RAW text.

    Telegram caps captions at 1024 chars; when exceeded the media is sent bare
    and the full text follows as separate message(s).
    """
    if len(raw_text) <= TG_CAPTION_LIMIT:
        kwargs = dict(extra)
        kwargs["caption"] = format_telegram_html(raw_text)
        kwargs.setdefault("parse_mode", "HTML")
        if media_type == 'photo':
            return await bot.send_photo(chat_id=chat_id, photo=media_file, **kwargs)
        elif media_type == 'video':
            return await bot.send_video(chat_id=chat_id, video=media_file, **kwargs)
        else:
            return await bot.send_document(chat_id=chat_id, document=media_file, **kwargs)

    # Caption too long: media first, full text as separate message(s)
    kwargs = {k: v for k, v in extra.items() if k != "parse_mode"}
    if media_type == 'photo':
        msg = await bot.send_photo(chat_id=chat_id, photo=media_file)
    elif media_type == 'video':
        msg = await bot.send_video(chat_id=chat_id, video=media_file)
    else:
        msg = await bot.send_document(chat_id=chat_id, document=media_file)

    try:
        text_msg = await send_long_message(bot, chat_id, raw_text, reply_markup=kwargs.get("reply_markup"))
    except Exception as e2:
        logger.error(f"[Bot] Long-text send failed: {e2}")
        text_msg = None
    return text_msg or msg


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


def cleanup_media(media_path: str | None, action: str) -> None:
    """Helper to clean up media files after publication or rejection."""
    if media_path and os.path.exists(media_path):
        try:
            os.remove(media_path)
            logger.info(f"[Bot] Файл {media_path} удален после {action}.")
        except Exception as e:
            logger.error(f"[Bot] Не удалось удалить файл {media_path}: {e}")


async def send_mod_card_to_chat(bot: Bot, chat_id: int, post):
    # RAW text: formatting/splitting happens inside the senders
    raw_text = (post.rewritten_text or post.text)[:TG_SAFE_MESSAGE_LIMIT]

    keyboard = build_mod_card_keyboard(post.id)

    chat_ids_to_send = [chat_id]

    # Если chat_id (обычно это группа) отличается от админского ID (лички), отправляем в оба
    if settings.ADMIN_IDS and str(settings.ADMIN_IDS[0]) != str(chat_id):
        chat_ids_to_send.append(settings.ADMIN_IDS[0])

    for target_chat_id in set(chat_ids_to_send):
        sent = False
        if post.media_path and post.media_type:
            abs_media_path = os.path.abspath(post.media_path)
            if os.path.exists(abs_media_path):
                try:
                    media_file = FSInputFile(abs_media_path)
                    await send_media_with_caption(
                        bot, target_chat_id,
                        post.media_type, media_file, raw_text,
                        reply_markup=keyboard
                    )
                    sent = True
                except Exception as e:
                    logger.error(f"[Bot] Error sending media to {target_chat_id}: {e}")

        if not sent:
            try:
                await bot.send_message(chat_id=target_chat_id, text=format_telegram_html(raw_text), reply_markup=keyboard, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"[Bot] HTML card failed for {target_chat_id}, falling back to plain text: {e}")
                try:
                    await bot.send_message(chat_id=target_chat_id, text=strip_html(raw_text)[:4096], reply_markup=keyboard)
                except Exception as e2:
                    if "group chat was upgraded to a supergroup chat" in str(e2) or "group chat was upgraded to a supergroup chat" in str(e):
                        logger.error(f"[Bot] effective_moderator_chat_id is outdated due to supergroup migration. Please update .env!")
                    logger.error(f"[Bot] Fallback send failed: {e2}")

    # Отправляем ссылки и источник отдельным СМС в конце
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
        # Escape URLs: raw & breaks Telegram HTML parsing
        links_formatted = "\n".join([f"• {escape(l)}" for l in extra_links])
        extra_parts.append(f"{i18n.get('extra_links')}\n{links_formatted}")
    if post.source_link:
        extra_parts.append(i18n.get('source_link', url=escape(post.source_link, quote=True)))

    if extra_parts:
        extra_text = "\n\n".join(extra_parts)
        for target_chat_id in set(chat_ids_to_send):
            try:
                await bot.send_message(chat_id=target_chat_id, text=extra_text, parse_mode="HTML", disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"[Bot] Error sending extra links to {target_chat_id}: {e}")
