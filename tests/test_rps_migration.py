import asyncio
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.db.models import Challenge, Chat, GameSession, PointEvent, User
from bot.db.session import create_engine, create_session_factory
from bot.utils.time import utc_now

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "c113a5aa0013"
CURRENT = "c115a5aa0015"


async def migrate(url, command, target):
    return await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", command, target],
        cwd=ROOT,
        env=os.environ | {"DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=60,
    )


async def seeded_previous(path):
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    result = await migrate(url, "upgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(url)
    sessions = create_session_factory(engine)
    try:
        async with sessions.begin() as session:
            session.add(Chat(id=-1, title="Existing", bot_is_admin=True))
            session.add(User(id=1, first_name="<User>"))
        async with sessions.begin() as session:
            session.add(
                GameSession(
                    id=15,
                    chat_id=-1,
                    started_by=1,
                    game="hyj",
                    status="finished",
                    state={"phase": "done", "target": 1},
                )
            )
        async with sessions.begin() as session:
            session.add(
                Challenge(
                    id=11,
                    chat_id=-1,
                    user_id=1,
                    kind="text",
                    status="done",
                    prompt_key="existing",
                    game_session_id=15,
                    deadline_at=utc_now(),
                )
            )
            session.add(PointEvent(chat_id=-1, user_id=1, delta=5, reason="test", ref_id="game:15"))
    finally:
        await engine.dispose()
    return url


async def test_populated_parent_rebuild_preserves_dares_ids_points_indexes_and_foreign_keys(
    tmp_path,
):
    path = tmp_path / "linked.db"
    url = await seeded_previous(path)
    for command, target in [("upgrade", "head"), ("downgrade", PREVIOUS), ("upgrade", "head")]:
        result = await migrate(url, command, target)
        assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(url)
    sessions = create_session_factory(engine)
    try:
        async with sessions() as session:
            game = await session.get(GameSession, 15)
            assert game.state == {"phase": "done", "target": 1}
            assert (await session.get(Challenge, 11)).game_session_id == 15
            assert (await session.scalars(select(PointEvent))).one().delta == 5
        async with engine.connect() as connection:
            assert (await connection.exec_driver_sql("PRAGMA foreign_keys")).scalar() == 1
            assert not (await connection.exec_driver_sql("PRAGMA foreign_key_check")).all()
            names = {
                row[1]
                for row in (
                    await connection.exec_driver_sql("PRAGMA index_list(game_sessions)")
                ).all()
            }
            assert {"ix_game_sessions_status_deadline", "uq_game_sessions_active_chat"} <= names
        with pytest.raises(IntegrityError):
            async with sessions.begin() as session:
                session.add(GameSession(chat_id=-999, started_by=1, game="rps"))
        async with sessions.begin() as session:
            session.add(GameSession(chat_id=-1, started_by=1, game="rps"))
    finally:
        await engine.dispose()
    refused = await migrate(url, "downgrade", PREVIOUS)
    assert (
        refused.returncode != 0
        and "Cannot downgrade while rps game history exists" in refused.stderr
    )
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == CURRENT
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM game_sessions WHERE game='rps'").fetchone()[0]
            == 1
        )


async def test_foreign_key_validation_failure_rolls_back_table_rebuild_and_revision(tmp_path):
    path = tmp_path / "invalid.db"
    url = await seeded_previous(path)
    # Only this temporary test DB is deliberately damaged to prove fail-closed
    # migration behavior; production/runtime FK enforcement is never disabled.
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE challenges SET game_session_id=999 WHERE id=11")
    result = await migrate(url, "upgrade", "head")
    assert result.returncode != 0 and "Migration foreign-key validation failed" in result.stderr
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == PREVIOUS
        )
        ddl = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='game_sessions'"
        ).fetchone()[0]
        assert "'rps'" not in ddl
        assert (
            connection.execute("SELECT game_session_id FROM challenges WHERE id=11").fetchone()[0]
            == 999
        )
        assert connection.execute("SELECT id FROM game_sessions").fetchall() == [(15,)]
