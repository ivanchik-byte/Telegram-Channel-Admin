from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import ProcessedPost
import logging
import sqlalchemy.exc

logger = logging.getLogger("TG_Admin")

class PostRepository:
    @staticmethod
    async def process_new_post(session: AsyncSession, channel_id: int, message_id: int, post_hash: str, text: str, status: str = 'seen'):
        """
        Uses atomic UPSERT (insert ... on conflict do nothing) to prevent race conditions.
        """
        # Atomic insert using postgresql dialect
        stmt = insert(ProcessedPost).values(
            source_channel_id=channel_id,
            source_message_id=message_id,
            post_hash=post_hash,
            text=text,
            status=status
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
    async def update_status(session: AsyncSession, post_id: int, new_status: str):
        from sqlalchemy import update
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id).values(status=new_status)
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def get_post_text(session: AsyncSession, post_id: int):
        stmt = select(ProcessedPost.text).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def update_post_success(session: AsyncSession, post_id: int, rewritten_text: str):
        from sqlalchemy import update
        stmt = update(ProcessedPost).where(ProcessedPost.id == post_id).values(
            rewritten_text=rewritten_text, 
            status='processed'
        )
        await session.execute(stmt)
        await session.commit()

    @staticmethod
    async def get_post_by_id(session: AsyncSession, post_id: int):
        stmt = select(ProcessedPost).where(ProcessedPost.id == post_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def atomic_status_update(session: AsyncSession, post_id: int, required_current_status: str, new_status: str):
        from sqlalchemy import update
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
        from sqlalchemy import update
        stmt = update(ProcessedPost).where(
            ProcessedPost.id == post_id,
            ProcessedPost.status == required_current_status
        ).values(rewritten_text=new_text).returning(ProcessedPost)
        result = await session.execute(stmt)
        post = result.scalars().first()
        await session.commit()
        return post
