"""Engine/session lifecycle. Only Alembic creates or changes tables."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def create_engine(database_url: str, *, pool_size: int = 15) -> AsyncEngine:
    options = (
        {"pool_size": pool_size, "max_overflow": 0} if database_url.startswith("postgresql") else {}
    )
    engine = create_async_engine(database_url, pool_pre_ping=True, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
