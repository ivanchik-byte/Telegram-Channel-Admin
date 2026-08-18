import asyncio
import re
import hashlib
from datetime import timedelta

from openai import AsyncOpenAI, APIStatusError, APIConnectionError, APITimeoutError
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
    Sends moderation card. 
    Uses the common logic send_mod_card_to_chat from bot/handlers.
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


async def _call_ai_with_retry(client: AsyncOpenAI, text: str, post_id: int, system_prompt: str | None = None) -> str | None:
    """AI rewrite with exponential backoff. Returns rewritten text or None on failure."""
    if not system_prompt:
        from src.core.prompts import SYSTEM_PROMPT_REWRITE
        system_prompt = SYSTEM_PROMPT_REWRITE

    backoff_delays = [2, 4, 8]

    for attempt, delay in enumerate(backoff_delays):
        try:
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                extra_body=settings.AI_EXTRA_BODY or {},
                timeout=60.0
            )
            content = response.choices[0].message.content
            return content.strip() if content else None

        except (APITimeoutError, asyncio.TimeoutError) as e:
            logger.error(f"[Worker] Пост {post_id}: Таймаут ожидания ответа ИИ ({settings.AI_MODEL} на {settings.AI_BASE_URL}): {e}")
            if attempt < len(backoff_delays) - 1:
                logger.warning(f"[Worker] Пост {post_id}: Повторная попытка через {delay} сек...")
                await asyncio.sleep(delay)
            else:
                break
        except APIStatusError as e:
            logger.error(f"[Worker] Пост {post_id}: Ошибка API ИИ ({e.status_code}): {e.message}")
            if e.status_code == 429 or (500 <= e.status_code < 600):
                if attempt < len(backoff_delays) - 1:
                    logger.warning(f"[Worker] Пост {post_id}: Повтор через {delay} сек...")
                    await asyncio.sleep(delay)
                    continue
            break
        except APIConnectionError as e:
            logger.error(f"[Worker] Пост {post_id}: Ошибка соединения с ИИ API ({settings.AI_BASE_URL}): {e}")
            if attempt < len(backoff_delays) - 1:
                logger.warning(f"[Worker] Пост {post_id}: Повтор через {delay} сек...")
                await asyncio.sleep(delay)
                continue
            break
        except Exception as e:
            logger.error(f"[Worker] Пост {post_id}: Ошибка при запросе к ИИ: {e}")
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

        settings_obj = await SettingsRepository.get_settings(session)
        now = datetime.now(timezone.utc)

        # Check global pause
        if settings_obj.pause_until and settings_obj.pause_until > now:
            logger.debug(f"[Worker] Бот на паузе до {settings_obj.pause_until}. Откладываем пост {post_id} на 60 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=60))
            return

        if settings_obj.next_post_time and settings_obj.next_post_time > now:
            delay = (settings_obj.next_post_time - now).total_seconds()
            jitter = random.uniform(1.0, 5.0)
            defer_sec = delay + jitter
            logger.info(f"[Worker] Интервал не прошел. Откладываем пост {post_id} на {defer_sec:.1f} сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=defer_sec))
            return

        # Check moderation limits
        mod_count, queued_count = await PostRepository.get_queue_counts(session)
        if settings_obj.mode == 'auto' and mod_count >= 1:
            logger.info(f"[Worker] В авторежиме уже есть пост на модерации. Откладываем пост {post_id} на 60 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=60))
            return

        # Reserve post atomically
        post = await PostRepository.atomic_status_update(session, post_id, 'queued', 'ai_processing')
        if not post:
            logger.info(f"[Worker] Пост {post_id} перехвачен другим воркером или изменил статус.")
            return

        post_text = post.text
        post_source_channel_id = post.source_channel_id
        post_media_path = post.media_path
        post_media_type = post.media_type
        post_source_link = post.source_link

        # Deduplication: search for a previously added post with the same hash
        duplicate_check_stmt = select(ProcessedPost).where(
            ProcessedPost.post_hash == post.post_hash,
            ProcessedPost.id < post.id
        ).limit(1)
        is_duplicate = (await session.execute(duplicate_check_stmt)).scalar() is not None

        if is_duplicate:
            logger.info(f"[Worker] Пост {post_id} определен как дубликат.")

            # Search for the original with already prepared rewritten_text
            orig_stmt = select(ProcessedPost).where(
                ProcessedPost.post_hash == post.post_hash,
                ProcessedPost.id != post.id,
                ProcessedPost.rewritten_text.is_not(None)
            ).order_by(ProcessedPost.id.asc()).limit(1)
            orig_result = await session.execute(orig_stmt)
            orig_post = orig_result.scalars().first()

            if not orig_post:
                # Original is still processing — check if it exists at all
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

            # Copy rewritten_text and immediately move to 'moderating'
            await PostRepository.update_post_ready_for_moderation(session, post_id, orig_post.rewritten_text)
            logger.info(f"[Worker] Пост {post_id} (дубликат) скопировал текст из поста {orig_post.id}.")
            duplicate_rewritten_text = orig_post.rewritten_text
            is_duplicate_ready = True

        else:
            # Ad filtering
            if contains_ad(post_text):
                logger.info(f"[Worker] Пост {post_id} отфильтрован как реклама.")
                await PostRepository.update_status(
                    session, post_id, 'filtered_ad', required_current_status='ai_processing'
                )
                return

            logger.info(f"[Worker] Пост {post_id} отправлен на AI-рерайт.")

        post_lang = getattr(settings_obj, 'post_lang', 'ru')

    # Session closed - now safe to make long network calls

    if is_duplicate_ready:
        await send_moderation_card(ctx, post_id, post_source_channel_id, duplicate_rewritten_text, post_media_path, post_media_type, post_source_link)
        return

    # --- Step 2: AI-rewrite — DB session closed ---
    from src.core.prompts import get_system_prompt
    client: AsyncOpenAI = ctx['ai_client']
    sys_prompt = get_system_prompt(post_lang)
    rewritten_text = await _call_ai_with_retry(client, post_text, post_id, system_prompt=sys_prompt)


    # --- Step 3: Finalization — new session ---
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
        
        # Update next_post_time after successful send


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
            await send_notification_to_all(ctx['bot'], i18n.get('worker_no_posts', hours=hours), requester_chat_id=requester_chat_id)
            return

        post_data = [{"id": p.id, "text": p.text[:500]} for p in posts]
        
    if getattr(settings, 'LANGUAGE', 'ru') == 'en':
        prompt = "Below is a list of posts. Choose up to 6 of the most interesting, viral, and useful posts. Return ONLY their numerical IDs comma-separated, without extra words, in descending order of interest (most awesome first).\n\n" + str(post_data)
    else:
        prompt = "Ниже список постов. Выбери до 6 самых интересных, виральных и полезных постов. Верни ТОЛЬКО их числовые ID через запятую, без лишних слов, в порядке убывания интересности (самый крутой - первый).\n\n" + str(post_data)
    
    client: AsyncOpenAI = ctx['ai_client']
    try:
        response = await client.chat.completions.create(
            model=settings.AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            extra_body=settings.AI_EXTRA_BODY or {},
            timeout=60.0
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

    best_post_id = best_ids[0]
    other_best_ids = best_ids[1:]

    # 1. Process the best post immediately
    async with async_session_maker() as session:
        stmt = select(ProcessedPost).where(ProcessedPost.id == best_post_id)
        result = await session.execute(stmt)
        best_post = result.scalars().first()
        
        if best_post and best_post.status in ['queued', 'accumulated']:
            best_post = await PostRepository.atomic_status_update(session, best_post.id, best_post.status, 'ai_processing')
            
    if best_post:
        from src.worker.tasks import _call_ai_with_retry
        from src.core.prompts import get_system_prompt
        async with async_session_maker() as session:
            best_settings = await SettingsRepository.get_settings(session)
            best_post_lang = getattr(best_settings, 'post_lang', 'ru')
        best_sys_prompt = get_system_prompt(best_post_lang)
        rewritten = await _call_ai_with_retry(client, best_post.text, best_post.id, system_prompt=best_sys_prompt)

        if rewritten:
            async with async_session_maker() as session:
                await PostRepository.update_post_ready_for_moderation(session, best_post.id, rewritten)
                await send_moderation_card(ctx, best_post.id, best_post.source_channel_id, rewritten, best_post.media_path, best_post.media_type, best_post.source_link)
        else:
            async with async_session_maker() as session:
                await PostRepository.update_status(session, best_post.id, 'failed')

    # 2. Queue the remaining best posts and mark the rest as filtered_ad
    async with async_session_maker() as session:
        for p in posts:
            if p.id == best_post_id:
                continue
            if p.id in other_best_ids:
                await PostRepository.update_status(session, p.id, 'queued')
                await ctx['redis'].enqueue_job('process_post_task', p.id)
            else:
                await PostRepository.update_status(session, p.id, 'filtered_ad')
                
    if best_ids:
        from src.bot.handlers import send_notification_to_all
        await send_notification_to_all(
            ctx['bot'], 
            i18n.get('worker_best_selected', selected=len(best_ids), total=len(posts), queued=len(other_best_ids)), 
            requester_chat_id=requester_chat_id
        )

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
