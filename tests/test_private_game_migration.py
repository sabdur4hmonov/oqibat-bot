import sqlite3

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_rps_migration import migrate, seeded_previous

from bot.db.models import Challenge, GameSession, PointEvent
from bot.db.session import create_engine, create_session_factory


async def test_background_index_upgrade_preserves_linked_history_and_independent_slots(tmp_path):
    path = tmp_path / "background.db"
    url = await seeded_previous(path)
    result = await migrate(url, "upgrade", "c118a5aa0018")
    assert result.returncode == 0, result.stderr
    engine = create_engine(url)
    sessions = create_session_factory(engine)
    try:
        async with sessions.begin() as session:
            assert (await session.get(Challenge, 11)).game_session_id == 15
            assert (await session.scalars(select(PointEvent))).one().delta == 5
            for kind in ("secret", "number", "duel"):
                session.add(GameSession(chat_id=-1, started_by=1, game=kind, status="lobby"))
        for kind in ("secret", "math", "unknown"):
            with pytest.raises(IntegrityError):
                async with sessions.begin() as session:
                    session.add(GameSession(chat_id=-1, started_by=1, game=kind, status="running"))
        refused = await migrate(url, "downgrade", "c116a5aa0016")
        assert refused.returncode != 0 and "Cannot remove secret game history" in refused.stderr
    finally:
        await engine.dispose()
    with sqlite3.connect(path) as connection:
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            == "c118a5aa0018"
        )
