from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.core.config import settings

# engine configured for asyncpg
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# session maker
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    """Creates tables that don't exist yet.

    Schema changes live in alembic migrations (docker-compose runs the migrator
    service before bot/worker/parser) — no ad-hoc ALTERs here to avoid two
    sources of truth for the schema.
    """
    from src.database.models import Base
    from src.core.logger import logger
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.warning(f"init_db execution warning: {e}")
