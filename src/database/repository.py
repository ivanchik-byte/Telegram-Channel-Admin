from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import ProcessedPost
from datetime import datetime, timezone
import logging

logger = logging.getLogger("TG_Admin")

class PostRepository:
    @staticmethod
    async def process_new_post(session: AsyncSession, channel_id: int, message_id: int, post_hash: str, text: str, media_path: str | None = None, media_type: str | None = None, source_link: str | None = None, status: str = 'seen'):
        """
        Атомарный UPSERT: insert ... on conflict do nothing.
        Возвращает id нового поста или None при дубликате.
        """
        stmt = insert(ProcessedPost).values(
            source_channel_id=channel_id,
            source_message_id=message_id,
            post_hash=post_hash,
            text=text,
            media_path=media_path,
            media_type=media_type,
            source_link=source_link,
            status=status,
            created_at=datetime.now(timezone.utc)
        ).on_conflict_do_nothing(
            index_elements=['source_channel_id', 'source_message_id']
        ).returning(ProcessedPost.id)

        try:
            result = await session.execute(stmt)
            post_id = result.scalars().first()
            await session.commit()
            return post_id
        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving post to DB: {e}")
            raise

    @staticmethod
    async def update_status(session: AsyncSession, post_id: int, new_status: str, required_current_status: str | None = None):
        """
        Обновляет статус поста.
        Если указан required_current_status — UPDATE срабатывает только при совпадении текущего статуса,
        защищая от гонок при ретраях arq.
        """
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id)
        if required_current_status is not None:
            stmt = stmt.where(ProcessedPost.status == required_current_status)
        stmt = stmt.values(status=new_status)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_post_ready_for_moderation(session: AsyncSession, post_id: int, rewritten_text: str, required_current_status: str | None = None):
        """Атомарно сохраняет rewritten_text и переводит пост в 'moderating'."""
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id)
        if required_current_status is not None:
            stmt = stmt.where(ProcessedPost.status == required_current_status)
        stmt = stmt.values(
            rewritten_text=rewritten_text,
            status='moderating'
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_post_by_id(session: AsyncSession, post_id: int):
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def atomic_status_update(session: AsyncSession, post_id: int, required_current_status: str, new_status: str):
        """UPDATE WHERE status = required → new_status. Возвращает пост или None (не прошёл условие)."""
        stmt = update(ProcessedPost).where(
            ProcessedPost.id == post_id,
            ProcessedPost.status == required_current_status
        ).values(status=new_status).returning(ProcessedPost)
        result = await session.execute(stmt)
        post = result.scalars().first()
        await session.commit()
        return post

    @staticmethod
    async def atomic_edit_text(session: AsyncSession, post_id: int, required_current_status: str, new_text: str):
        """UPDATE WHERE status = required → new rewritten_text. Возвращает пост или None."""
        stmt = update(ProcessedPost).where(
            ProcessedPost.id == post_id,
            ProcessedPost.status == required_current_status
        ).values(rewritten_text=new_text).returning(ProcessedPost)
        result = await session.execute(stmt)
        post = result.scalars().first()
        await session.commit()
        return post

    @staticmethod
    async def atomic_update_media(session: AsyncSession, post_id: int, required_current_status: str, media_path: str | None, media_type: str | None):
        """UPDATE WHERE status = required → new media_path and media_type. Возвращает пост или None."""
        stmt = update(ProcessedPost).where(
            ProcessedPost.id == post_id,
            ProcessedPost.status == required_current_status
        ).values(media_path=media_path, media_type=media_type).returning(ProcessedPost)
        result = await session.execute(stmt)
        post = result.scalars().first()
        await session.commit()
        return post

    @staticmethod
    async def get_queue_counts(session: AsyncSession):
        """Returns tuple: (moderating_count, queued_count)"""
        from sqlalchemy import func
        stmt = select(ProcessedPost.status, func.count(ProcessedPost.id)).where(
            ProcessedPost.status.in_(['moderating', 'queued', 'ai_processing'])
        ).group_by(ProcessedPost.status)
        
        result = await session.execute(stmt)
        counts = {'moderating': 0, 'queued': 0, 'ai_processing': 0}
        for row in result.all():
            counts[row[0]] = row[1]
            
        return counts['moderating'] + counts['ai_processing'], counts['queued']


from src.database.models import BotSettings
from datetime import datetime

class SettingsRepository:
    @staticmethod
    async def get_settings(session: AsyncSession) -> BotSettings:
        stmt = select(BotSettings).where(BotSettings.id == 1)
        result = await session.execute(stmt)
        settings = result.scalars().first()
        if not settings:
            settings = BotSettings()
            session.add(settings)
            await session.commit()
        return settings

    @staticmethod
    async def update_settings(session: AsyncSession, **kwargs):
        settings = await SettingsRepository.get_settings(session)
        for key, value in kwargs.items():
            setattr(settings, key, value)
        await session.commit()
        return settings
