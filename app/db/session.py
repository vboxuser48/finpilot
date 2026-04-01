from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

async_engine = create_async_engine(settings.async_database_uri, echo=False, future=True)

AsyncSessionMaker = async_sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields an async session."""

    async with AsyncSessionMaker() as session:
        yield session
