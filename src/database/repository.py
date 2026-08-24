from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import ProcessedPost, BotSettings
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger("TG_Admin")

class PostRepository:
    @staticmethod
    async def process_new_post(session: AsyncSession, channel_id: int, message_id: int, post_hash: str, text: str, media_path: str | None = None, media_type: str | None = None, source_link: str | None = None, status: str = 'seen'):
        """
        Atomic UPSERT: insert ... on conflict do nothing.
        Returns new post id or None on duplicate.
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
    async def update_status(session: AsyncSession, post_id: int, new_status: str, required_current_status: str | list[str] | None = None):
        """
        Updates post status.
        If required_current_status is specified — UPDATE only triggers when current status matches,
        protecting against races during arq retries.
        Leaving 'ai_processing' also clears the stale lock timestamp.
        """
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id)
        if required_current_status is not None:
            statuses = [required_current_status] if isinstance(required_current_status, str) else required_current_status
            stmt = stmt.where(ProcessedPost.status.in_(statuses))
        values = {'status': new_status}
        if new_status != 'ai_processing':
            values['locked_at'] = None
        stmt = stmt.values(**values)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    @staticmethod
    async def update_post_ready_for_moderation(session: AsyncSession, post_id: int, rewritten_text: str, required_current_status: str | list[str] | None = None):
        """Atomically saves rewritten_text and moves post to 'moderating' (clears the lock)."""
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id)
        if required_current_status is not None:
            statuses = [required_current_status] if isinstance(required_current_status, str) else required_current_status
            stmt = stmt.where(ProcessedPost.status.in_(statuses))
        stmt = stmt.values(
            rewritten_text=rewritten_text,
            status='moderating',
            locked_at=None
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
    async def atomic_status_update(session: AsyncSession, post_id: int, required_current_status: str | list[str], new_status: str, set_lock: bool = False):
        """UPDATE WHERE status IN required -> new_status. Returns post or None (condition failed)."""
        statuses = [required_current_status] if isinstance(required_current_status, str) else required_current_status
        values = {'status': new_status}
        if set_lock:
            values['locked_at'] = datetime.now(timezone.utc)
        stmt = update(ProcessedPost).where(
            ProcessedPost.id == post_id,
            ProcessedPost.status.in_(statuses)
        ).values(**values).returning(ProcessedPost)
        result = await session.execute(stmt)
        post = result.scalars().first()
        await session.commit()
        return post

    @staticmethod
    async def requeue_stale_processing(session: AsyncSession, stale_after_seconds: int) -> list[int]:
        """Reaper for posts stuck in 'ai_processing' (crashed worker/bot mid-AI-call).

        Resets them to 'queued' so the pipeline is not blocked forever.
        Returns the ids of requeued posts (caller must re-enqueue their jobs).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        stmt = (
            update(ProcessedPost)
            .where(
                ProcessedPost.status == 'ai_processing',
                ProcessedPost.locked_at.is_not(None),
                ProcessedPost.locked_at < cutoff
            )
            .values(status='queued', locked_at=None)
            .returning(ProcessedPost.id)
        )
        result = await session.execute(stmt)
        await session.commit()
        return list(result.scalars().all())

    @staticmethod
    async def atomic_edit_text(session: AsyncSession, post_id: int, required_current_status: str, new_text: str):
        """UPDATE WHERE status = required -> new rewritten_text. Returns post or None."""
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
        """UPDATE WHERE status = required -> new media_path and media_type. Returns post or None."""
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
        """Returns tuple: (in_moderation_count [moderating + ai_processing], queued_count)"""
        from sqlalchemy import func
        stmt = select(ProcessedPost.status, func.count(ProcessedPost.id)).where(
            ProcessedPost.status.in_(['moderating', 'queued', 'ai_processing'])
        ).group_by(ProcessedPost.status)
        
        result = await session.execute(stmt)
        counts = {'moderating': 0, 'queued': 0, 'ai_processing': 0}
        for row in result.all():
            counts[row[0]] = row[1]
            
        return counts['moderating'] + counts['ai_processing'], counts['queued']


class SettingsRepository:
    @staticmethod
    async def get_settings(session: AsyncSession) -> BotSettings:
        """Reads (or race-safely creates) the settings row.

        Note: does NOT touch the global i18n state — a DB read must not flip
        the UI language mid-request. Language changes go through update_settings,
        initial sync happens at process startup.
        """
        from src.core.config import settings as env_settings

        default_lang = getattr(env_settings, 'LANGUAGE', 'ru')

        stmt = select(BotSettings).where(BotSettings.id == 1)
        result = await session.execute(stmt)
        bot_settings = result.scalars().first()
        if bot_settings:
            # Repair legacy NULL languages; commit explicitly so the ORM object
            # never carries hidden dirty state into a later update_settings
            repaired = False
            if not bot_settings.ui_lang:
                bot_settings.ui_lang = default_lang
                repaired = True
            if not bot_settings.post_lang:
                bot_settings.post_lang = default_lang
                repaired = True
            if repaired:
                await session.commit()
            return bot_settings

        # Row missing (first run): race-safe insert, then re-read.
        # The upsert runs once per process lifetime, not on every read.
        await session.execute(
            insert(BotSettings).values(id=1).on_conflict_do_nothing(index_elements=['id'])
        )
        await session.commit()

        result = await session.execute(stmt)
        bot_settings = result.scalars().first()
        if not bot_settings:
            # Still nothing (extremely unlikely) — create via ORM fallback
            bot_settings = BotSettings(id=1, ui_lang=default_lang, post_lang=default_lang)
            session.add(bot_settings)
            await session.commit()
        return bot_settings

    @staticmethod
    async def sync_i18n_language(session: AsyncSession):
        """Explicit startup sync of the global UI language from the DB."""
        from src.core.i18n import i18n
        bot_settings = await SettingsRepository.get_settings(session)
        i18n.set_language(bot_settings.ui_lang)

    @staticmethod
    async def update_settings(session: AsyncSession, **kwargs):
        from src.core.i18n import i18n
        bot_settings = await SettingsRepository.get_settings(session)
        for key, value in kwargs.items():
            setattr(bot_settings, key, value)
        await session.commit()
        if 'ui_lang' in kwargs:
            i18n.set_language(kwargs['ui_lang'])
        return bot_settings

