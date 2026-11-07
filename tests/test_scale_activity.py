from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import event, select

from bot.db.models import Chat, Membership, User
from bot.services.activity import ActivityBuffer


async def test_1000_messages_do_no_sql_then_two_bulk_upserts(sessions):
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov"))
    statements = []
    engine = sessions.kw["bind"].sync_engine

    def listener(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", listener)
    buffer = ActivityBuffer(sessions)
    now = datetime(2026, 11, 7, tzinfo=UTC)
    try:
        for i in range(1000):
            buffer.observe(
                -1, 42, "Old" if i < 999 else "New", "new_name", now + timedelta(seconds=i)
            )
        buffer.observe(-999, 43, "Unknown group", None, now)
        assert statements == []
        await buffer.flush()
        assert len(statements) == 2
        assert all("ON CONFLICT" in sql for sql in statements)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    async with sessions() as session:
        assert (await session.get(User, 42)).first_name == "New"
        member = await session.get(Membership, (-1, 42))
        assert member.last_seen_at == now + timedelta(seconds=999)
        assert not member.opted_in
        assert await session.get(Chat, -999) is None
        assert await session.get(Membership, (-999, 43)) is None


async def test_buffer_preserves_opt_in_and_private_flags(sessions):
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov"))
        session.add(User(id=42, first_name="Old", started_private=True))
        await session.flush()
        session.add(Membership(chat_id=-1, user_id=42, opted_in=True))
    buffer = ActivityBuffer(sessions)
    buffer.observe(-1, 42, "New", None)
    await buffer.flush()
    async with sessions() as session:
        assert (await session.get(User, 42)).started_private
        assert (await session.get(Membership, (-1, 42))).opted_in
    buffer.mark_private(42, "New", None)
    await buffer.mark_forbidden(42)
    await buffer.flush()
    async with sessions() as session:
        assert not (await session.get(User, 42)).started_private


async def test_failed_flush_retains_rows_and_newer_observations(sessions):
    buffer = ActivityBuffer(sessions)
    buffer.observe(-1, 42, "Old", None)

    async def fail(*args, **kwargs):
        buffer.observe(-1, 42, "New", "new")
        raise RuntimeError("offline")

    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new=AsyncMock(side_effect=fail)):
        with pytest.raises(RuntimeError, match="offline"):
            await buffer.flush()
    assert buffer.users[42]["first_name"] == "New"
    await buffer.flush()
    async with sessions() as session:
        assert (await session.get(User, 42)).first_name == "New"


async def test_chunked_buffer_flush_does_not_exceed_sqlite_limits(sessions):
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov"))
    buffer = ActivityBuffer(sessions)
    for user in range(350):
        buffer.observe(-1, user + 1, "Sinov", None)
    await buffer.flush()
    async with sessions() as session:
        assert len((await session.scalars(select(Membership))).all()) == 350
