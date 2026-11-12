"""Opt-in smoke test for a NEW, EMPTY, LOCAL database named oqibat_verify_* only."""

import asyncio
import os
import subprocess
import sys
from datetime import UTC, time, timedelta
from pathlib import Path

import pytest
from aiogram.types import User as TelegramUser
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from bot.db.models import Chat, GameSession, Membership, PointEvent
from bot.db.repo.challenges import ChallengeRepository
from bot.db.repo.games import Award, GameSessionRepository
from bot.db.repo.groups import GroupRepository
from bot.db.session import create_engine, create_session_factory
from bot.services.activity import ActivityBuffer
from bot.services.game_cache import GameCache
from bot.services.locks import ChatLocks
from bot.services.participation import Participants
from bot.services.pending import PendingChallenges
from bot.services.points import Points
from bot.services.scheduler import Scheduler
from bot.services.weekly import summary
from bot.utils.time import utc_now, week_start

ROOT = Path(__file__).resolve().parents[1]


async def test_postgres_migrations_utc_bulk_upserts_ledger_games_and_due_queries():
    raw = os.environ.get("OQIBAT_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Set OQIBAT_TEST_DATABASE_URL to a new empty LOCAL oqibat_verify_* DB")
    url = make_url(raw)
    assert url.drivername == "postgresql+asyncpg"
    assert url.host in {"127.0.0.1", "localhost"}, "Local verification database only"
    assert url.database and url.database.startswith("oqibat_verify_"), "Refusing non-test database"
    engine = create_engine(raw, pool_size=10)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        assert not tables, (
            "Refusing to migrate a non-empty database; create a fresh verification DB"
        )
        for arguments in (["upgrade", "head"], ["check"]):
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "alembic", *arguments],
                cwd=ROOT,
                env=os.environ | {"DATABASE_URL": raw},
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        sessions = create_session_factory(engine)
        locks, pending, participants, cache = (
            ChatLocks(),
            PendingChallenges(),
            Participants(),
            GameCache(),
        )
        groups = GroupRepository(sessions, locks, pending, participants, cache)
        now = utc_now()
        async with sessions.begin() as session:
            session.add(
                Chat(
                    id=-1000001234567,
                    title="PostgreSQL smoke",
                    bot_is_admin=True,
                    quiet_start=time(),
                    quiet_end=time(),
                )
            )
        chat_id = -1000001234567
        await groups.membership(
            chat_id, TelegramUser(id=42, is_bot=False, first_name="Oʻtkir"), opted_in=True
        )
        activity = ActivityBuffer(sessions)
        activity.observe(chat_id, 42, "Gʻulom", "smoke_user", now)
        await activity.flush()
        async with sessions() as session:
            member = await session.get(Membership, (chat_id, 42))
            assert member.opted_in and member.last_seen_at.utcoffset() == timedelta(0)
            assert not (await session.get(Chat, chat_id)).mafia_delete_dead_messages
        points = Points(sessions, locks)
        assert await points.award(chat_id, 42, 5, "smoke", "smoke:once")
        assert not await points.award(chat_id, 42, 5, "smoke", "smoke:once")
        tasks = ChallengeRepository(sessions, pending, locks, cache)
        result = await tasks.assign(
            chat_id, now, [{"key": "smoke_text", "kind": "text", "text": "Smoke"}], force=True
        )
        challenge, _, _, _ = result
        await tasks.set_message(chat_id, challenge.id, 1)
        assert (
            await tasks.complete(chat_id, challenge.id, 42, "text", now + timedelta(seconds=1), 2)
            == 5
        )
        assert not pending.for_chat(chat_id)
        games = GameSessionRepository(sessions, locks, cache, pending)
        game = await games.start(
            chat_id, 42, "quiz", {"phase": "question"}, now + timedelta(seconds=30)
        )
        with pytest.raises(IntegrityError):
            async with sessions.begin() as session:
                session.add(
                    GameSession(chat_id=chat_id, game="krokodil", status="running", started_by=42)
                )
                await session.flush()

        def finish(row):
            row.status, row.phase_deadline_at = "finished", None
            row.state["phase"] = "done"
            return [Award(42, 2, "game_smoke", f"game:{row.id}")]

        finished = await games.transition(chat_id, game.id, finish, expected_rev=game.state["rev"])
        assert finished.status == "finished" and cache.main(chat_id) is None
        assert await games.claim_result_card(chat_id, game.id)
        assert not await games.claim_result_card(chat_id, game.id)
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.sum(PointEvent.delta)).where(PointEvent.chat_id == chat_id)
                )
                == 12
            )
            report = await summary(
                session, chat_id, week_start(now, "Asia/Tashkent"), now + timedelta(minutes=1)
            )
            assert report["top"][0].points == 12 and report["active"].activities == 3
        async with sessions.begin() as session:
            (await session.get(Chat, chat_id)).next_daily_at = now

        async def hook(chat, current_time):
            return True

        scheduler = Scheduler(sessions, hooks={"daily": hook})
        assert (await scheduler.tick(now))["daily"] == 1
        async with sessions() as session:
            stored = (await session.get(Chat, chat_id)).next_daily_at
            assert stored > now and stored.tzinfo == UTC
        assert engine.pool.size() == 10 and engine.pool._max_overflow == 0
        rps = await games.start(
            chat_id,
            42,
            "rps",
            {"phase": "choosing", "players": [42, 43]},
            now + timedelta(seconds=60),
        )

        def rps_finish(row):
            row.status, row.phase_deadline_at = "finished", None
            row.state.update(phase="done", winner=42)
            return [Award(42, 2, "rps", f"game:{row.id}")]

        assert (await games.transition(chat_id, rps.id, rps_finish)).status == "finished"
        assert await games.transition(chat_id, rps.id, rps_finish) is None
        assert (await points.stats(chat_id, 42))[0] == 14
        for kind, delta in (("number", 3), ("math", 2)):
            quick = await games.start(
                chat_id, 42, kind, {"phase": "playing"}, now + timedelta(seconds=20)
            )

            def finish_quick(row, kind=kind, delta=delta):
                row.status, row.phase_deadline_at = "finished", None
                row.state.update(phase="done", winner=42)
                return [Award(42, delta, kind, f"game:{row.id}")]

            assert (await games.transition(chat_id, quick.id, finish_quick)).status == "finished"
            assert await games.transition(chat_id, quick.id, finish_quick) is None
        assert (await points.stats(chat_id, 42))[0] == 19
    finally:
        await engine.dispose()
