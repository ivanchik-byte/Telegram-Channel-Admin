from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import settings

# engine configured for asyncpg
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# session maker
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    from src.database.models import Base
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS queue_limit INTEGER DEFAULT 5;"))
        except Exception:
            pass
