from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import settings
from src.core.logger import logger
import os
import asyncio

# engine configured for asyncpg
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# session maker
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    from src.database.models import Base
    async with engine.begin() as conn:
        # We will create tables if they don't exist (for fresh starts)
        await conn.run_sync(Base.metadata.create_all)
