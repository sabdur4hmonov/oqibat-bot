"""Async migrations use DATABASE_URL only; no Telegram credentials required."""

import asyncio
from logging.config import fileConfig

from alembic import context

from bot.config import DatabaseSettings
from bot.db.models import Base, UTCDateTime
from bot.db.session import create_engine

if context.config.config_file_name:
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=DatabaseSettings().database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_engine(DatabaseSettings().database_url.get_secret_value())
    try:
        async with engine.connect() as connection:
            if connection.dialect.name == "sqlite":
                # Alembic batch rebuilds a parent table by copying/dropping it.
                # Suspend FKs on this migration-only connection outside a DB
                # transaction, then use explicit transactional DDL and validate
                # all references before commit. Runtime connections keep FKs ON.
                await connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
                await connection.commit()
                try:
                    await connection.exec_driver_sql("BEGIN")
                    await connection.run_sync(do_run_migrations)
                    if (await connection.exec_driver_sql("PRAGMA foreign_key_check")).first():
                        raise RuntimeError("Migration foreign-key validation failed")
                    await connection.commit()
                except BaseException:
                    await connection.rollback()
                    raise
                finally:
                    await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                    await connection.commit()
            else:
                await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
