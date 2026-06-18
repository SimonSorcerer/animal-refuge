from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_host = urlparse(settings.database_url).hostname or ""
_needs_ssl = _host not in ("localhost", "127.0.0.1") and not _host.endswith(".internal")
_connect_args = {"ssl": "require"} if _needs_ssl else {}

engine = create_async_engine(settings.database_url, echo=False, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
