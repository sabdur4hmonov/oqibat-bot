import sqlite3

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from test_rps_migration import migrate, seeded_previous

from bot.db.models import Challenge, GameSession, PointEvent
from bot.db.session import create_engine, create_session_factory

CURRENT = "c116a5aa0016"
PREVIOUS = "c115a5aa0015"


async def test_new_types_upgrade_preserves_links_refuses_lossy_downgrade_and_keeps_foreign_keys(
    tmp_path,
):
    path = tmp_path / "quick_games.db"
    url = await seeded_previous(path)
    result = await migrate(url, "upgrade", CURRENT)
    assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(url)
    sessions = create_session_factory(engine)
    try:
        async with sessions() as session:
            assert (await session.get(Challenge, 11)).game_session_id == 15
            assert (await session.get(GameSession, 15)).state == {"phase": "done", "target": 1}
            assert (await session.scalars(select(PointEvent))).one().delta == 5
        async with sessions.begin() as session:
            for kind in ("number", "math"):
                session.add(GameSession(chat_id=-1, started_by=1, game=kind, status="finished"))
        with pytest.raises(IntegrityError):
            async with sessions.begin() as session:
                session.add(GameSession(chat_id=-1, started_by=1, game="unknown"))
        with pytest.raises(IntegrityError):
            async with sessions.begin() as session:
                session.add(GameSession(chat_id=-999, started_by=1, game="number"))
        refused = await migrate(url, "downgrade", PREVIOUS)
        assert refused.returncode != 0 and "Cannot downgrade while number/math" in refused.stderr
        with sqlite3.connect(path) as connection:
            assert (
                connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                == CURRENT
            )
        # Only new rows in this temporary test DB have no dependent history.
        async with sessions.begin() as session:
            await session.execute(
                delete(GameSession).where(GameSession.game.in_(["number", "math"]))
            )
    finally:
        await engine.dispose()
    for command, target in [("downgrade", PREVIOUS), ("upgrade", CURRENT)]:
        result = await migrate(url, command, target)
        assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert (
            connection.execute("SELECT game_session_id FROM challenges WHERE id=11").fetchone()[0]
            == 15
        )
