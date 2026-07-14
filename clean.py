import asyncio
from src.database.engine import async_session_maker
from src.database.models import ProcessedPost
from sqlalchemy import delete

async def main():
    async with async_session_maker() as session:
        stmt = delete(ProcessedPost)
        result = await session.execute(stmt)
        await session.commit()
        print(f"Deleted {result.rowcount} posts.")

if __name__ == "__main__":
    asyncio.run(main())
