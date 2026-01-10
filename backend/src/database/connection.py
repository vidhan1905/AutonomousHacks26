"""Database connection and session management."""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.src.config import settings

# Use database URL from settings (which reads from environment)
DATABASE_URL = settings.database_url

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


def create_async_session_maker():
    """Create a fresh async session maker for a new event loop."""
    # Re-import settings to get latest database_url
    from backend.src.config import settings
    fresh_engine = create_async_engine(settings.database_url, echo=True)
    return async_sessionmaker(fresh_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
