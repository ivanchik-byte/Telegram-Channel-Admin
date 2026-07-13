import asyncio
import re
import hashlib
from datetime import timedelta

from openai import AsyncOpenAI, APIStatusError, APIConnectionError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.enums import ParseMode
from html import escape

from src.core.logger import logger
from src.core.config import settings
from src.core.prompts import SYSTEM_PROMPT_REWRITE
from src.core.i18n import i18n
from src.core.constants import TG_SAFE_MESSAGE_LIMIT
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from sqlalchemy import select
from src.database.models import ProcessedPost


def contains_ad(text: str) -> bool:
    if not text or not settings.parsed_ad_keywords:
        return False

    text_lower = text.lower()
    for kw in settings.parsed_ad_keywords:
        # Substring match is intentional for Russian morphology:
        # "реклама" matches "рекламы", "рекламе", "рекламой" etc.
        if kw in text_lower:
            return True
    return False


async def send_moderation_card(ctx, post_id: int, source_channel_id: int, text: str, media_path: str | None = None, media_type: str | None = None):
    """
    Отправляет карточку модерации в MODERATOR_CHAT_ID.
    Статус поста уже выставлен в 'moderating' вызывающим кодом до вызова этой функции.
    При сбое отправки — только логирует ошибку, НЕ меняет статус.
    Пост остаётся в 'moderating' с сохранённым rewritten_text.
    """
    # escape user content before embedding into HTML message
    display_text = escape(text[:TG_SAFE_MESSAGE_LIMIT])
    text_to_send = f"{i18n.get('card_new_post', channel_id=source_channel_id)}\n\n{display_text}"

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

    try:
        bot = ctx['bot']
        if media_path and media_type:
            try:
                media_file = FSInputFile(media_path)
                if media_type == 'photo':
                    await bot.send_photo(
                        chat_id=settings.MODERATOR_CHAT_ID,
                        photo=media_file,
                        caption=text_to_send,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                elif media_type == 'video':
                    await bot.send_video(
                        chat_id=settings.MODERATOR_CHAT_ID,
                        video=media_file,
                        caption=text_to_send,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await bot.send_document(
                        chat_id=settings.MODERATOR_CHAT_ID,
                        document=media_file,
                        caption=text_to_send,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                logger.info(f"[Worker] Пост {post_id} с медиа отправлен на модерацию.")
                return
            except Exception as e:
                logger.error(f"[Worker] Ошибка отправки медиа для поста {post_id}: {e}. Отправляем как текст.")
                # Fallback to text if media sending fails
                
        await bot.send_message(
            chat_id=settings.MODERATOR_CHAT_ID,
            text=text_to_send,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"[Worker] Пост {post_id} отправлен на модерацию (текст).")
    except Exception as e:
        # Статус не меняем: пост в 'moderating' с rewritten_text, можно восстановить.
        logger.error(f"[Worker] Не удалось отправить карточку модерации для поста {post_id}: {e}")


async def _call_ai_with_retry(client: AsyncOpenAI, text: str, post_id: int) -> str | None:
    """AI rewrite with exponential backoff. Returns rewritten text or None on failure."""
    backoff_delays = [2, 4, 8, 16, 32]

    for attempt, delay in enumerate(backoff_delays):
        try:
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_REWRITE},
                    {"role": "user", "content": text}
                ],
                extra_body=settings.AI_EXTRA_BODY or {}
            )
            return response.choices[0].message.content.strip()

        except APIStatusError as e:
            if e.status_code == 429 or (500 <= e.status_code < 600):
                if attempt < len(backoff_delays) - 1:
                    logger.warning(f"[Worker] Пост {post_id}: Ошибка {e.status_code}. Повтор через {delay} сек...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[Worker] Пост {post_id}: Исчерпаны лимиты ожидания (RateLimit/Server Error).")
            else:
                logger.error(f"[Worker] Пост {post_id}: Критическая ошибка API: {e.status_code} - {e.message}")
            break
        except APIConnectionError:
            if attempt < len(backoff_delays) - 1:
                logger.warning(f"[Worker] Пост {post_id}: Ошибка соединения. Повтор через {delay} сек...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[Worker] Пост {post_id}: Исчерпаны лимиты ожидания (Connection).")
            break
        except Exception as e:
            logger.error(f"[Worker] Пост {post_id}: Неизвестная ошибка: {e}")
            break

    return None


async def process_post_task(ctx, post_id: int):
    logger.info(f"[Worker] Получена задача на обработку поста с ID: {post_id}")
    
    from src.database.repository import SettingsRepository
    from datetime import datetime, timezone
    import random
    
    async with async_session_maker() as session:
        settings = await SettingsRepository.get_settings(session)
        now = datetime.now(timezone.utc)
        if settings.next_post_time and settings.next_post_time > now:
            delay = (settings.next_post_time - now).total_seconds()
            jitter = random.uniform(1.0, 5.0)
            defer_sec = delay + jitter
            logger.info(f"[Worker] Интервал не прошел. Откладываем пост {post_id} на {defer_sec:.1f} сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=defer_sec))
            return

    # --- Шаг 1: Читаем данные, дедупликация, начальная фильтрация — закрываем сессию ---
    # Сессия НЕ держится открытой во время AI-запроса (backoff до ~62 сек).
    post_text: str | None = None
    post_source_channel_id: int | None = None
    is_duplicate_ready = False
    duplicate_rewritten_text: str | None = None

    async with async_session_maker() as session:
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        post = result.scalars().first()

        if not post or not post.text:
            logger.warning(f"[Worker] Пост {post_id} не найден или не содержит текста.")
            return

        post_text = post.text
        post_source_channel_id = post.source_channel_id
        post_media_path = post.media_path
        post_media_type = post.media_type

        # Дедупликация: ищем ранее добавленный пост с тем же хэшем
        duplicate_check_stmt = select(ProcessedPost).where(
            ProcessedPost.post_hash == post.post_hash,
            ProcessedPost.id < post.id
        ).limit(1)
        is_duplicate = (await session.execute(duplicate_check_stmt)).scalar() is not None

        if is_duplicate:
            logger.info(f"[Worker] Пост {post_id} определен как дубликат.")

            # Ищем оригинал с уже готовым rewritten_text
            orig_stmt = select(ProcessedPost).where(
                ProcessedPost.post_hash == post.post_hash,
                ProcessedPost.id != post.id,
                ProcessedPost.rewritten_text.is_not(None)
            ).order_by(ProcessedPost.id.asc()).limit(1)
            orig_result = await session.execute(orig_stmt)
            orig_post = orig_result.scalars().first()

            if not orig_post:
                # Оригинал ещё обрабатывается — проверяем, существует ли он вообще
                any_orig_stmt = select(ProcessedPost).where(
                    ProcessedPost.post_hash == post.post_hash,
                    ProcessedPost.id != post.id
                ).limit(1)
                any_result = await session.execute(any_orig_stmt)
                orig_any = any_result.scalars().first()
                if orig_any:
                    if orig_any.status in ('failed', 'filtered_ad', 'rejected'):
                        logger.info(f"[Worker] Оригинал {post_id} забракован (статус {orig_any.status}). Дубликат отменён.")
                        await PostRepository.update_status(session, post_id, orig_any.status)
                        return
                        
                    logger.warning(
                        f"[Worker] Оригинал для дубликата {post_id} еще в обработке. "
                        f"Откладываем на 30 сек."
                    )
                    # Re-enqueue with delay instead of raising RuntimeError (which caused blind retries)
                    await ctx['redis'].enqueue_job(
                        'process_post_task', post_id, _defer_by=timedelta(seconds=30)
                    )
                    return
                else:
                    logger.error(f"[Worker] Оригинал для дубликата {post_id} не найден. Отмена.")
                    await PostRepository.update_status(session, post_id, 'failed')
                    return

            # Копируем rewritten_text и сразу переводим в 'moderating'
            await PostRepository.update_post_ready_for_moderation(session, post_id, orig_post.rewritten_text)
            logger.info(f"[Worker] Пост {post_id} (дубликат) скопировал текст из поста {orig_post.id}.")
            duplicate_rewritten_text = orig_post.rewritten_text
            is_duplicate_ready = True

        else:
            # Фильтрация рекламы
            if contains_ad(post_text):
                logger.info(f"[Worker] Пост {post_id} отфильтрован как реклама.")
                await PostRepository.update_status(
                    session, post_id, 'filtered_ad', required_current_status='queued'
                )
                return

            success = await PostRepository.update_status(
                session, post_id, 'ai_processing', required_current_status='queued'
            )
            if not success:
                logger.warning(f"[Worker] Пост {post_id} изменил статус. Отмена.")
                return
                
            logger.info(f"[Worker] Пост {post_id} отправлен на AI-рерайт.")

    # Сессия закрыта — теперь безопасно делать долгие сетевые вызовы

    if is_duplicate_ready:
        await send_moderation_card(ctx, post_id, post_source_channel_id, duplicate_rewritten_text, post_media_path, post_media_type)
        return

    # --- Шаг 2: AI-рерайт — БД-сессия закрыта ---
    client: AsyncOpenAI = ctx['ai_client']
    rewritten_text = await _call_ai_with_retry(client, post_text, post_id)

    # --- Шаг 3: Финализация — новая сессия ---
    async with async_session_maker() as session:
        if rewritten_text:
            success = await PostRepository.update_post_ready_for_moderation(
                session, post_id, rewritten_text, required_current_status='ai_processing'
            )
            if success:
                logger.info(f"[Worker] Пост {post_id} успешно обработан ИИ и готов к модерации.")
            else:
                logger.warning(f"[Worker] Пост {post_id} изменил статус во время генерации текста. Результат отброшен.")
                rewritten_text = None
        else:
            await PostRepository.update_status(
                session, post_id, 'failed', required_current_status='ai_processing'
            )
            logger.error(f"[Worker] Пост {post_id} переведен в статус failed.")

    if rewritten_text:
        await send_moderation_card(ctx, post_id, post_source_channel_id, rewritten_text, post_media_path, post_media_type)
        
        # Обновляем next_post_time после успешной отправки
        from src.database.repository import SettingsRepository
        from datetime import datetime, timezone
        import random
        async with async_session_maker() as session:
            settings = await SettingsRepository.get_settings(session)
            if settings.interval_min > 0 or settings.interval_max > 0:
                delay_seconds = random.randint(settings.interval_min, max(settings.interval_min, settings.interval_max))
                next_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
                await SettingsRepository.update_settings(session, next_post_time=next_time)
                logger.info(f"[Worker] Следующий пост будет отправлен не раньше чем через {delay_seconds} секунд.")


async def find_best_post_task(ctx, hours: int):
    logger.info(f"[Worker] Поиск лучшего поста за последние {hours} часов...")
    from src.database.repository import SettingsRepository
    from datetime import datetime, timezone
    
    async with async_session_maker() as session:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = select(ProcessedPost).where(
            ProcessedPost.status == 'accumulated',
            ProcessedPost.created_at >= since
        )
        result = await session.execute(stmt)
        posts = result.scalars().all()
        
        if not posts:
            logger.info("[Worker] Нет постов для выбора.")
            bot = ctx['bot']
            await bot.send_message(settings.MODERATOR_CHAT_ID, f"Нет накопленных постов за последние {hours}ч.")
            return

        post_data = [{"id": p.id, "text": p.text[:500]} for p in posts]
        
    prompt = "Ниже список постов. Выбери ОДИН самый интересный, виральный и полезный пост. Верни ТОЛЬКО его числовой ID, без лишних слов и символов.\n\n" + str(post_data)
    
    client: AsyncOpenAI = ctx['ai_client']
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body=settings.AI_EXTRA_BODY or {}
        )
        best_id_str = response.choices[0].message.content.strip()
        # Ищем число в ответе (иногда ИИ может написать "ID: 123")
        import re
        match = re.search(r'\d+', best_id_str)
        if match:
            best_id = int(match.group())
        else:
            raise ValueError(f"Нет числа в ответе: {best_id_str}")
    except Exception as e:
        logger.error(f"[Worker] Ошибка при выборе лучшего поста: {e}")
        return

    # Process best_id, mark others as filtered_ad
    async with async_session_maker() as session:
        found = False
        for p in posts:
            if p.id == best_id:
                found = True
                await PostRepository.update_status(session, p.id, 'queued')
                await ctx['redis'].enqueue_job('process_post_task', p.id)
            else:
                await PostRepository.update_status(session, p.id, 'filtered_ad')
                
        if found:
            bot = ctx['bot']
            await bot.send_message(settings.MODERATOR_CHAT_ID, f"Выбран лучший пост из {len(posts)} кандидатов. Ожидайте рерайт.")
        else:
            logger.error(f"[Worker] Выбранный ID {best_id} не найден в списке!")
