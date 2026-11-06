from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ted.infrastructure.persistence.schema import metadata as metadata
from ted.infrastructure.runtime import settings

engine = create_async_engine(
    settings.database_url, pool_size=5, max_overflow=5, hide_parameters=True
)
sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
