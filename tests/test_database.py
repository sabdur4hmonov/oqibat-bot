import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError

from bot.db.models import Chat, GameSession, ScheduledPost, User
from bot.db.session import create_engine


def test_migration_upgrade_is_idempotent_and_no_schema_drift(database_url):
    for args in (["upgrade", "head"], ["check"]):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            env=os.environ | {"DATABASE_URL": database_url},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr


async def test_all_tables_exist(database_url):
    engine = create_engine(database_url)
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        assert tables == {
            "chats",
            "users",
            "memberships",
            "point_events",
            "challenges",
            "content_usage",
            "scheduled_posts",
            "game_sessions",
            "alembic_version",
        }
    finally:
        await engine.dispose()


async def test_defaults_and_utc_roundtrip(sessions):
    local = datetime(2026, 11, 7, 15, 0, tzinfo=timezone(timedelta(hours=5)))
    async with sessions.begin() as session:
        session.add(Chat(id=-1001234567890, title="Sinov", created_at=local))
    async with sessions() as session:
        chat = await session.get(Chat, -1001234567890)
        assert chat.created_at == datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
        assert chat.created_at.tzinfo == UTC
        assert chat.tz == "Asia/Tashkent"
        assert chat.penalty_mode == "points"
        assert chat.challenges_per_day == 1
        assert chat.bot_is_admin is False


async def test_naive_timestamps_rejected(sessions):
    with pytest.raises(StatementError, match="timezone-aware"):
        async with sessions.begin() as session:
            session.add(User(id=1, first_name="Test", created_at=datetime(2026, 1, 1)))


async def seed(sessions):
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov"))
        session.add(User(id=1, first_name="Test"))


async def test_only_one_active_non_duel_session_per_chat(sessions):
    await seed(sessions)
    async with sessions.begin() as session:
        session.add(GameSession(chat_id=-1, game="quiz", started_by=1))
        session.add(GameSession(chat_id=-1, game="duel", started_by=1))
        session.add(GameSession(chat_id=-1, game="duel", started_by=1))
        session.add(GameSession(chat_id=-1, game="quiz", status="finished", started_by=1))
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(GameSession(chat_id=-1, game="mafia", status="running", started_by=1))


async def test_duplicate_scheduled_posts_and_unknown_chat_rejected(sessions):
    await seed(sessions)
    async with sessions.begin() as session:
        session.add(ScheduledPost(chat_id=-1, kind="daily", local_date=datetime.now(UTC).date()))
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(
                ScheduledPost(chat_id=-1, kind="daily", local_date=datetime.now(UTC).date())
            )
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(GameSession(chat_id=-999, game="quiz", started_by=1))
    async with sessions() as session:
        assert len((await session.scalars(select(ScheduledPost))).all()) == 1
