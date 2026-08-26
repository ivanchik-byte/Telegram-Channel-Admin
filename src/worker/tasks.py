import asyncio
from datetime import timedelta

from openai import AsyncOpenAI, APIStatusError, APIConnectionError, APITimeoutError
from aiogram import Bot
from src.core.ai_notifier import notify_ai_error

from src.core.logger import logger
from src.core.config import settings
from src.core.prompts import SYSTEM_PROMPT_REWRITE
from src.core.i18n import i18n
from src.core.adfilter import contains_ad  # re-exported for backwards compatibility
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from sqlalchemy import select
from src.database.models import ProcessedPost

# How long a post may sit in 'ai_processing' before the stale-lock reaper
# considers the worker dead and requeues it.
STALE_LOCK_SECONDS = 30 * 60
# How long a duplicate may wait for its original to finish processing
# before giving up (protects against infinite 30s deferral loops).
DUPLICATE_MAX_WAIT = timedelta(hours=6)



async def send_moderation_card(ctx, post_id: int):
    """
    Sends moderation card.
    Uses the common messaging layer (no aiogram Router dependency).
    """
    from src.bot.messaging import send_mod_card_to_chat

    async with async_session_maker() as session:
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        post = result.scalars().first()
        if not post:
            logger.error(f"[Worker] Пост {post_id} не найден при отправке карточки.")
            return

    try:
        # Telegram API accepts both numeric IDs and @usernames — no int() cast,
        # which used to crash on @username moderator chats
        chat_id = settings.effective_moderator_chat_id.strip()
        if chat_id:
            await send_mod_card_to_chat(ctx['bot'], chat_id, post)
        else:
            logger.error("[Worker] effective_moderator_chat_id пустой, некуда отправлять карточку модерации.")
    except Exception as e:
        logger.error(f"[Worker] Не удалось отправить пост {post_id} на модерацию: {e}")


async def _call_ai_with_retry(
    client: AsyncOpenAI,
    text: str,
    post_id: int,
    system_prompt: str | None = None,
    bot: Bot | None = None
) -> str | None:
    """AI rewrite with exponential backoff and Telegram error notifications."""
    if not system_prompt:
        system_prompt = SYSTEM_PROMPT_REWRITE

    backoff_delays = [2, 4, 8]
    last_exception: Exception | None = None

    for attempt, delay in enumerate(backoff_delays):
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Вот исходный черновик/материал для поста:\n\n{text}\n\nНапиши на его основе полноценный пост для Telegram в соответствии с инструкциями."}
            ]
            response = await client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=messages,
                extra_body=settings.AI_EXTRA_BODY or {},
                timeout=180.0
            )
            content = response.choices[0].message.content
            if content:
                from src.core.utils import clean_post_output
                content = clean_post_output(content)
            return content if content else None
        except (APITimeoutError, asyncio.TimeoutError) as e:
            last_exception = e
            logger.error(f"[Worker] Пост {post_id}: Таймаут ожидания ответа ИИ ({settings.AI_MODEL} на {settings.AI_BASE_URL}): {e}")
            if attempt < len(backoff_delays) - 1:
                logger.warning(f"[Worker] Пост {post_id}: Повторная попытка через {delay} сек...")
                await asyncio.sleep(delay)
            else:
                break
        except APIStatusError as e:
            last_exception = e
            logger.error(f"[Worker] Пост {post_id}: Ошибка API ИИ ({e.status_code}): {e.message}")
            if e.status_code == 429 or (500 <= e.status_code < 600):
                if attempt < len(backoff_delays) - 1:
                    logger.warning(f"[Worker] Пост {post_id}: Повтор через {delay} сек...")
                    await asyncio.sleep(delay)
                    continue
            break
        except APIConnectionError as e:
            last_exception = e
            logger.error(f"[Worker] Пост {post_id}: Ошибка соединения с ИИ API ({settings.AI_BASE_URL}): {e}")
            if attempt < len(backoff_delays) - 1:
                logger.warning(f"[Worker] Пост {post_id}: Повтор через {delay} сек...")
                await asyncio.sleep(delay)
                continue
            break
        except Exception as e:
            last_exception = e
            logger.error(f"[Worker] Пост {post_id}: Ошибка при запросе к ИИ: {e}")
            break

    if last_exception and bot:
        try:
            await notify_ai_error(bot, last_exception, post_id=post_id)
        except Exception as notify_err:
            logger.error(f"[Worker] Ошибка при отправке уведомления в Telegram: {notify_err}")

    return None


async def process_post_task(ctx, post_id: int):
    logger.info(f"[Worker] Получена задача на обработку поста с ID: {post_id}")
    
    from src.database.repository import SettingsRepository
    from datetime import datetime, timezone
    import random
    
    post_text: str | None = None
    is_duplicate_ready = False

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
            logger.debug(f"[Worker] Бот на паузе до {settings_obj.pause_until}. Откладываем пост {post_id} на 15 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=15))
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
            logger.info(f"[Worker] В авторежиме уже есть пост на модерации. Откладываем пост {post_id} на 15 сек.")
            await ctx['redis'].enqueue_job('process_post_task', post_id, _defer_by=timedelta(seconds=15))
            return

        # Reserve post atomically (also stamps locked_at for the stale-lock reaper)
        post = await PostRepository.atomic_status_update(
            session, post_id, 'queued', 'ai_processing', set_lock=True
        )
        if not post:
            logger.info(f"[Worker] Пост {post_id} перехвачен другим воркером или изменил статус.")
            return

        post_text = post.text

        # Deduplication: search for a previously added post with the same hash
        duplicate_check_stmt = select(ProcessedPost).where(
            ProcessedPost.post_hash == post.post_hash,
            ProcessedPost.id < post.id
        ).limit(1)
        is_duplicate = (await session.execute(duplicate_check_stmt)).scalar() is not None

        if is_duplicate:
            logger.info(f"[Worker] Пост {post_id} определен как дубликат.")

            if datetime.now(timezone.utc) - post.created_at > DUPLICATE_MAX_WAIT:
                logger.error(f"[Worker] Дубликат {post_id} ждал оригинал слишком долго. Отмена.")
                await PostRepository.update_status(session, post_id, 'failed', required_current_status='ai_processing')
                return

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
        custom_prompt = getattr(settings_obj, 'custom_prompt', None)

    # Session closed - now safe to make long network calls

    if is_duplicate_ready:
        await send_moderation_card(ctx, post_id)
        return

    # --- Step 2: AI-rewrite — DB session closed ---
    from src.core.prompts import get_system_prompt
    client: AsyncOpenAI = ctx['ai_client']
    sys_prompt = get_system_prompt(post_lang, custom_prompt)
    rewritten_text = await _call_ai_with_retry(
        client, post_text, post_id, system_prompt=sys_prompt, bot=ctx.get('bot')
    )


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
        await send_moderation_card(ctx, post_id)
        
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
            from src.bot.messaging import send_notification_to_all
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
        if not matches:
            raise ValueError(f"Нет чисел в ответе: {best_ids_str}")
    except Exception as e:
        logger.error(f"[Worker] Ошибка при выборе лучшего поста: {e}")
        if ctx.get('bot'):
            try:
                await notify_ai_error(ctx.get('bot'), e)
            except Exception as notif_err:
                logger.error(f"[Worker] Ошибка отправки уведомления: {notif_err}")
        return

    # LLMs hallucinate IDs: keep only numbers that are real candidates,
    # otherwise a single invented ID would get every post marked as ad
    candidate_ids = {p.id for p in posts}
    best_ids = [int(m) for m in matches if int(m) in candidate_ids][:6]
    if not best_ids:
        logger.error(f"[Worker] ИИ вернул только несуществующие ID: {matches}. Посты не тронуты.")
        from src.bot.messaging import send_notification_to_all
        await send_notification_to_all(
            ctx['bot'],
            i18n.get('worker_best_invalid', total=len(posts)),
            requester_chat_id=requester_chat_id
        )
        return

    best_post_id = best_ids[0]
    other_best_ids = set(best_ids[1:])

    # 1. Process the best post immediately (guarded acquisition)
    async with async_session_maker() as session:
        best_post = await PostRepository.atomic_status_update(
            session, best_post_id, ['queued', 'accumulated'], 'ai_processing', set_lock=True
        )

    if best_post:
        from src.core.prompts import get_system_prompt
        async with async_session_maker() as session:
            best_settings = await SettingsRepository.get_settings(session)
            best_post_lang = getattr(best_settings, 'post_lang', 'ru')
            best_custom_prompt = getattr(best_settings, 'custom_prompt', None)
        best_sys_prompt = get_system_prompt(best_post_lang, best_custom_prompt)
        rewritten = await _call_ai_with_retry(
            client, best_post.text, best_post.id, system_prompt=best_sys_prompt, bot=ctx.get('bot')
        )

        if rewritten:
            async with async_session_maker() as session:
                success = await PostRepository.update_post_ready_for_moderation(
                    session, best_post.id, rewritten, required_current_status='ai_processing'
                )
                if success:
                    await send_moderation_card(ctx, best_post.id)
        else:
            async with async_session_maker() as session:
                await PostRepository.update_status(session, best_post.id, 'failed', required_current_status='ai_processing')

    # 2. Queue the remaining selected posts and mark the rest as filtered_ad.
    # All transitions are guarded so we never clobber a status changed meanwhile.
    enqueued_count = 0
    async with async_session_maker() as session:
        for p in posts:
            if p.id == best_post_id:
                continue
            if p.id in other_best_ids:
                updated = await PostRepository.update_status(
                    session, p.id, 'queued', required_current_status='accumulated'
                )
                if updated:
                    await ctx['redis'].enqueue_job('process_post_task', p.id)
                    enqueued_count += 1
            else:
                for current in ('accumulated', 'queued'):
                    if await PostRepository.update_status(session, p.id, 'filtered_ad', required_current_status=current):
                        break

    from src.bot.messaging import send_notification_to_all
    await send_notification_to_all(
        ctx['bot'],
        i18n.get('worker_best_selected', selected=len(best_ids), total=len(posts), queued=enqueued_count),
        requester_chat_id=requester_chat_id
    )

async def requeue_stuck_posts_cron(ctx):
    """Reaper: posts stuck in 'ai_processing' (crashed worker mid-AI-call) go back to the queue.

    Without this, one crashed job blocks the whole auto-mode moderation slot forever.
    Re-enqueues the jobs so the posts actually get processed again.
    """
    async with async_session_maker() as session:
        requeued_ids = await PostRepository.requeue_stale_processing(session, STALE_LOCK_SECONDS)
    if requeued_ids:
        logger.warning(f"[Worker] Reaper: возвращено в очередь застрявших постов: {requeued_ids}")
        for pid in requeued_ids:
            await ctx['redis'].enqueue_job('process_post_task', pid)

async def clean_old_posts_cron(ctx):
    """Cron job to clean stale posts older than 48 hours.

    Only terminal-state posts are removed. Published post hashes are kept
    for deduplication; moderating/queued posts survive weekends untouched.
    """
    logger.info("[Worker] Запуск очистки базы от постов старше 48 часов...")
    from datetime import datetime, timezone, timedelta
    from src.core.utils import delete_media_file

    async with async_session_maker() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        stmt = select(ProcessedPost).where(
            ProcessedPost.created_at < cutoff,
            ProcessedPost.status.in_(['rejected', 'failed', 'filtered_ad'])
        )
        old_posts = list((await session.execute(stmt)).scalars().all())
        deleted_count = 0
        for old_post in old_posts:
            delete_media_file(old_post.media_path)
            await session.delete(old_post)
            deleted_count += 1
            # Commit per row so one failure doesn't lose already-deleted files' rows
            await session.commit()
        logger.info(f"[Worker] Очистка завершена. Удалено постов: {deleted_count}")
