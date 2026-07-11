import asyncio
import re
import openai
from openai import AsyncOpenAI
from src.core.logger import logger
from src.core.config import settings
from src.core.prompts import SYSTEM_PROMPT_REWRITE
from src.database.engine import async_session_maker
from src.database.repository import PostRepository
from sqlalchemy import select
from src.database.models import ProcessedPost

_ai_client = None

def get_ai_client() -> AsyncOpenAI:
    global _ai_client
    if _ai_client is None:
        _ai_client = AsyncOpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL)
    return _ai_client

def contains_ad(text: str) -> bool:
    if not text or not settings.parsed_ad_keywords:
        return False
    
    text_lower = text.lower()
    for kw in settings.parsed_ad_keywords:
        # Use look-behind and look-ahead for non-word chars instead of \b to support #, : etc.
        pattern = rf"(?:^|(?<=\W)){re.escape(kw)}(?:$|(?=\W))"
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            return True
    return False

async def send_moderation_card(ctx, session, post_id: int, source_channel_id: int, text: str):
    try:
        from aiogram import Bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.enums import ParseMode
        
        from src.core.i18n import i18n
        display_text = text[:4000]
        text_to_send = f"{i18n.get('card_new_post', channel_id=source_channel_id)}\n\n{display_text}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=i18n.get('btn_publish'), callback_data=f"publish_{post_id}"),
                InlineKeyboardButton(text=i18n.get('btn_reject'), callback_data=f"reject_{post_id}")
            ],
            [
                InlineKeyboardButton(text=i18n.get('btn_edit'), callback_data=f"edit_{post_id}")
            ]
        ])
        
        async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
            await bot.send_message(
                chat_id=settings.MODERATOR_CHAT_ID,
                text=text_to_send,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        
        await PostRepository.update_status(session, post_id, 'moderating')
        logger.info(f"[Worker] Пост {post_id} отправлен на модерацию.")
    except Exception as e:
        logger.error(f"[Worker] Ошибка отправки поста {post_id} на модерацию: {e}")
        await PostRepository.update_status(session, post_id, 'failed')

async def process_post_task(ctx, post_id: int):
    logger.info(f"[Worker] Получена задача на обработку поста с ID: {post_id}")
    
    async with async_session_maker() as session:
        # Fetch the entire post to check status
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        post = result.scalars().first()
        
        if not post or not post.text:
            logger.warning(f"[Worker] Пост {post_id} не найден или не содержит текста.")
            return



        text = post.text

        # 1. Ad filtering
        if contains_ad(text):
            logger.info(f"[Worker] Пост {post_id} отфильтрован как реклама.")
            await PostRepository.update_status(session, post_id, 'filtered_ad')
            return
            
        # Update status to ai_processing
        await PostRepository.update_status(session, post_id, 'ai_processing')
        logger.info(f"[Worker] Пост {post_id} отправлен на AI-рерайт.")

        # 2. AI Rewrite with Exponential Backoff
        max_retries = 5
        backoff_delays = [2, 4, 8, 16, 32]
        
        rewritten_text = None
        success = False
        
        client = get_ai_client()
        
        for attempt in range(max_retries):
            try:
                # Prepare arguments
                kwargs = {
                    "model": settings.AI_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT_REWRITE},
                        {"role": "user", "content": text}
                    ]
                }
                
                response = await client.chat.completions.create(
                    **kwargs, 
                    extra_body=settings.AI_EXTRA_BODY or {}
                )
                rewritten_text = response.choices[0].message.content.strip()
                success = True
                break
                
            except openai.APIStatusError as e:
                # Retry on 429 and 5xx errors
                if e.status_code == 429 or (500 <= e.status_code < 600):
                    if attempt < len(backoff_delays):
                        delay = backoff_delays[attempt]
                        logger.warning(f"[Worker] Пост {post_id}: Ошибка {e.status_code}. Повтор через {delay} сек...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"[Worker] Пост {post_id}: Исчерпаны лимиты ожидания (RateLimit/Server Error).")
                        break
                else:
                    logger.error(f"[Worker] Пост {post_id}: Критическая ошибка API: {e.status_code} - {e.message}")
                    break
            except openai.APIConnectionError as e:
                if attempt < len(backoff_delays):
                    delay = backoff_delays[attempt]
                    logger.warning(f"[Worker] Пост {post_id}: Ошибка соединения (APIConnectionError). Повтор через {delay} сек...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[Worker] Пост {post_id}: Исчерпаны лимиты ожидания (Connection).")
                    break
            except Exception as e:
                logger.error(f"[Worker] Пост {post_id}: Неизвестная ошибка: {e}")
                break
                
        # 3. Finalize
        if success and rewritten_text:
            await PostRepository.update_post_success(session, post_id, rewritten_text)
            logger.info(f"[Worker] Пост {post_id} успешно обработан и сохранен.")
            
            # Send moderation card
            await send_moderation_card(ctx, session, post_id, post.source_channel_id, rewritten_text)
        else:
            await PostRepository.update_status(session, post_id, 'failed')
            logger.error(f"[Worker] Пост {post_id} переведен в статус failed.")
