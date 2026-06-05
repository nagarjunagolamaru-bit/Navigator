from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings


def _build_engine() -> AsyncEngine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for vector database operations.")

    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


engine = _build_engine()
