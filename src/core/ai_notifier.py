import time
from html import escape
from aiogram import Bot
from openai import APIStatusError, APIConnectionError, APITimeoutError
from src.core.logger import logger
from src.core.config import settings
from src.core.i18n import i18n

# Cooldown cache to prevent spamming Telegram chat: (category, post_id_or_general) -> timestamp
_LAST_ALERT_TIMESTAMP: dict[tuple[str, str], float] = {}
_ALERT_COOLDOWN_SECONDS = 300.0  # 5 minutes cooldown per error type


def parse_ai_error(e: Exception | str) -> tuple[str, str, str]:
    """
    Categorizes an AI exception and returns (category, friendly_reason, technical_details).
    """
    err_str = str(e)

    if isinstance(e, APIStatusError):
        status = e.status_code
        if status == 410:
            return (
                "410_gone",
                i18n.get('ai_err_410'),
                f"HTTP 410: {e.message}"
            )
        elif status == 401:
            return (
                "401_unauthorized",
                i18n.get('ai_err_401'),
                f"HTTP 401: {e.message}"
            )
        elif status == 404:
            return (
                "404_not_found",
                i18n.get('ai_err_404'),
                f"HTTP 404: {e.message}"
            )
        elif status == 429:
            return (
                "429_quota",
                i18n.get('ai_err_429'),
                f"HTTP 429: {e.message}"
            )
        elif status == 402:
            return (
                "402_payment",
                i18n.get('ai_err_402'),
                f"HTTP 402: {e.message}"
            )
        elif 500 <= status < 600:
            return (
                "5xx_server_error",
                i18n.get('ai_err_5xx'),
                f"HTTP {status}: {e.message}"
            )
        else:
            return (
                f"http_{status}",
                f"Ошибка API (HTTP {status}): {e.message}",
                err_str
            )
    elif isinstance(e, APITimeoutError):
        return (
            "timeout",
            i18n.get('ai_err_timeout'),
            err_str
        )
    elif isinstance(e, APIConnectionError):
        return (
            "connection_error",
            i18n.get('ai_err_connection'),
            err_str
        )
    else:
        # Check string content for fallback matching
        if "410" in err_str or "Gone" in err_str or "end of life" in err_str.lower():
            return ("410_gone", i18n.get('ai_err_410'), err_str)
        elif "401" in err_str or "Unauthorized" in err_str:
            return ("401_unauthorized", i18n.get('ai_err_401'), err_str)
        elif "404" in err_str or "Not Found" in err_str:
            return ("404_not_found", i18n.get('ai_err_404'), err_str)
        elif "429" in err_str or "quota" in err_str.lower() or "rate limit" in err_str.lower():
            return ("429_quota", i18n.get('ai_err_429'), err_str)
        elif "timeout" in err_str.lower() or "таймаут" in err_str.lower():
            return ("timeout", i18n.get('ai_err_timeout'), err_str)
        elif "connection" in err_str.lower():
            return ("connection_error", i18n.get('ai_err_connection'), err_str)

        return ("unknown_error", f"Сбой при обращении к ИИ: {err_str[:150]}", err_str)


async def notify_ai_error(
    bot: Bot | None,
    error: Exception | str,
    post_id: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    force: bool = False
) -> bool:
    """
    Sends a formatted alert message to the moderator chat and admin PM about an AI failure.
    Includes throttling to avoid spamming when multiple posts fail in a row.
    """
    if not bot:
        logger.warning("[AI Notifier] Экземпляр бота не передан, пропуск отправки в Telegram.")
        return False

    cat, reason, raw_detail = parse_ai_error(error)
    active_model = model or settings.AI_MODEL
    active_base_url = base_url or settings.AI_BASE_URL

    now = time.time()
    cache_key = (cat, "post" if post_id else "global")
    if not force:
        last_sent = _LAST_ALERT_TIMESTAMP.get(cache_key, 0.0)
        if (now - last_sent) < _ALERT_COOLDOWN_SECONDS:
            logger.info(f"[AI Notifier] Кулдаун для типа ошибки '{cat}' активен. Пропуск повторного уведомления.")
            return False

    _LAST_ALERT_TIMESTAMP[cache_key] = now

    # Prepare readable details
    clean_detail = escape(raw_detail[:350] + ("..." if len(raw_detail) > 350 else ""))
    post_info = f"\n📝 <b>ID поста:</b> <code>#{post_id}</code>" if post_id else ""

    text = (
        f"🚨 <b>Внимание: Сбой генерации текста (AI API)</b>\n\n"
        f"❌ <b>Причина:</b> {reason}\n"
        f"🤖 <b>Модель:</b> <code>{escape(active_model)}</code>\n"
        f"🌐 <b>Эндпоинт:</b> <code>{escape(active_base_url)}</code>"
        f"{post_info}\n\n"
        f"📋 <b>Детали ошибки:</b>\n"
        f"<blockquote><code>{clean_detail}</code></blockquote>\n\n"
        f"💡 <b>Что делать:</b>\n"
        f"• Если модель устарела (410 / 404), укажите актуальную модель в <code>.env</code> (параметр <code>AI_MODEL</code>).\n"
        f"• Если ошибка авторизации (401 / 429), обновите <code>AI_API_KEY</code>.\n"
        f"• Для быстрой проверки отправьте команду <code>/test_ai</code> в бот."
    )

    chat_ids: list[int] = []
    if settings.effective_moderator_chat_id:
        chat_ids.append(settings.effective_moderator_chat_id)
    if settings.ADMIN_IDS:
        for admin_id in settings.ADMIN_IDS:
            if admin_id not in chat_ids:
                chat_ids.append(admin_id)

    sent_any = False
    for chat_id in chat_ids:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            sent_any = True
        except Exception as e:
            logger.error(f"[AI Notifier] Ошибка отправки уведомления в чат {chat_id}: {e}")

    if sent_any:
        logger.info(f"[AI Notifier] Уведомление об ошибке '{cat}' успешно отправлено в Telegram.")
    return sent_any
