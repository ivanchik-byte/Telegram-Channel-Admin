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


async def send_moderation_card(ctx, post_id: int, source_channel_id: int, text: str, media_path: str | None = None, media_type: str | None = None, source_link: str | None = None):
    """
    Отправляет карточку модерации. 
    Использует общую логику send_mod_card_to_chat из bot/handlers.
    """
    from src.bot.handlers import send_mod_card_to_chat
    
    async with async_session_maker() as session:
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        post = result.scalars().first()
        if not post:
            logger.error(f"[Worker] Пост {post_id} не найден при отправке карточки.")
            return

    try:
        chat_id = int(settings.effective_moderator_chat_id) if settings.effective_moderator_chat_id.strip() else 0
        if chat_id:
            await send_mod_card_to_chat(ctx['bot'], chat_id, post)
        else:
            logger.error("[Worker] effective_moderator_chat_id пустой, некуда отправлять карточку модерации.")
    except Exception as e:
        logger.error(f"[Worker] Ошибка при отправке карточки модерации: {e}")


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
    
    post_text: str | None = None
    post_source_channel_id: int | None = None
    is_duplicate_ready = False
    duplicate_rewritten_text: str | None = None

    async with async_session_maker() as session:
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        post = result.scalars().first()

        if not post or post.status != 'queued' or not post.text:
            logger.info(f"[Worker] Пост {post_id} не найден, не в статусе queued или не содержит текста. Игнорируем.")
            return

        settings = await SettingsRepository.get_settings(session)
        now = datetime.now(timezone.utc)

        # Check global pause
        if settings.pause_until and settings.pause_until > now:
            logger.debug(f"[Worker] Бот на паузе до {settings.pause_until}. Откладываем пост {post_id} на 60 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=60))
            return

        if settings.next_post_time and settings.next_post_time > now:
            delay = (settings.next_post_time - now).total_seconds()
            jitter = random.uniform(1.0, 5.0)
            defer_sec = delay + jitter
            logger.info(f"[Worker] Интервал не прошел. Откладываем пост {post_id} на {defer_sec:.1f} сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=defer_sec))
            return

        # Check moderation limits
        mod_count, queued_count = await PostRepository.get_queue_counts(session)
        if settings.mode == 'auto' and mod_count >= 1:
            logger.info(f"[Worker] В авторежиме уже есть пост на модерации. Откладываем пост {post_id} на 60 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=60))
            return

        # Резервируем пост атомарно
        post = await PostRepository.atomic_status_update(session, post_id, 'queued', 'ai_processing')
        if not post:
            logger.info(f"[Worker] Пост {post_id} перехвачен другим воркером или изменил статус.")
            return

        post_text = post.text
        post_source_channel_id = post.source_channel_id
        post_media_path = post.media_path
        post_media_type = post.media_type
        post_source_link = post.source_link

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
                    await PostRepository.update_status(session, post_id, 'queued', required_current_status='ai_processing')
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
                    session, post_id, 'filtered_ad', required_current_status='ai_processing'
                )
                return

            logger.info(f"[Worker] Пост {post_id} отправлен на AI-рерайт.")

    # Сессия закрыта — теперь безопасно делать долгие сетевые вызовы

    if is_duplicate_ready:
        await send_moderation_card(ctx, post_id, post_source_channel_id, duplicate_rewritten_text, post_media_path, post_media_type, post_source_link)
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
        await send_moderation_card(ctx, post_id, post_source_channel_id, rewritten_text, post_media_path, post_media_type, post_source_link)
        
        # Обновляем next_post_time после успешной отправки


async def find_best_post_task(ctx, hours: int, requester_chat_id: int | None = None):
    logger.info(f"[Worker] Поиск лучшего поста за последние {hours} часов...")
    from src.database.repository import SettingsRepository
    from datetime import datetime, timezone
    
    async with async_session_maker() as session:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = select(ProcessedPost).where(
            ProcessedPost.status.in_(['accumulated', 'queued']),
            ProcessedPost.created_at >= since
        )
        result = await session.execute(stmt)
        posts = result.scalars().all()
        
        if not posts:
            logger.info("[Worker] Нет постов для выбора.")
            from src.bot.handlers import send_notification_to_all
            await send_notification_to_all(ctx['bot'], f"Нет накопленных постов за последние {hours}ч.", requester_chat_id=requester_chat_id)
            return

        post_data = [{"id": p.id, "text": p.text[:500]} for p in posts]
        
    prompt = "Ниже список постов. Выбери до 6 самых интересных, виральных и полезных постов. Верни ТОЛЬКО их числовые ID через запятую, без лишних слов, в порядке убывания интересности (самый крутой - первый).\n\n" + str(post_data)
    
    client: AsyncOpenAI = ctx['ai_client']
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body=settings.AI_EXTRA_BODY or {}
        )
        best_ids_str = response.choices[0].message.content.strip()
        import re
        matches = re.findall(r'\d+', best_ids_str)
        if matches:
            best_ids = [int(m) for m in matches[:6]]
        else:
            raise ValueError(f"Нет чисел в ответе: {best_ids_str}")
    except Exception as e:
        logger.error(f"[Worker] Ошибка при выборе лучшего поста: {e}")
        return

    async with async_session_maker() as session:
        found_first = None
        for p in posts:
            if p.id in best_ids:
                if found_first is None and p.id == best_ids[0]:
                    found_first = p.id
                await PostRepository.update_status(session, p.id, 'queued')
                # Enqueue all selected posts
                await ctx['redis'].enqueue_job('process_post_task', p.id)
            else:
                await PostRepository.update_status(session, p.id, 'filtered_ad')
                
        if best_ids:
            from src.bot.handlers import send_notification_to_all
            await send_notification_to_all(ctx['bot'], f"Выбрано {len(best_ids)} постов из {len(posts)} кандидатов. Они отправлены в очередь на рерайт и публикацию.", requester_chat_id=requester_chat_id)
        else:
            logger.error(f"[Worker] Выбранные ID не найдены в списке!")

async def clean_old_posts_cron(ctx):
    """Cron job to clean posts older than 48 hours"""
    logger.info("[Worker] Запуск очистки базы от постов старше 48 часов...")
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import delete
    
    async with async_session_maker() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        stmt = delete(ProcessedPost).where(ProcessedPost.created_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        deleted_count = result.rowcount
        logger.info(f"[Worker] Очистка завершена. Удалено постов: {deleted_count}")
