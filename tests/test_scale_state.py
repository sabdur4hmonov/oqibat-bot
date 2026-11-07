import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.db.models import Chat, GameSession, User
from bot.db.repo.challenges import ChallengeRepository
from bot.db.repo.games import GameSessionRepository
from bot.services.admin_cache import AdminCache
from bot.services.locks import ChatLocks
from bot.services.metrics import Metrics
from bot.services.pending import PendingChallenges
from bot.utils.time import utc_now


async def test_admin_cache_ttl_and_coalesced_refresh(fake_clock):
    bot = SimpleNamespace(
        get_chat_administrators=AsyncMock(
            return_value=[SimpleNamespace(user=SimpleNamespace(id=7))]
        )
    )
    cache = AdminCache(bot, clock=fake_clock.now)
    assert all(ids == {7} for ids in await asyncio.gather(*[cache.get(-1) for _ in range(50)]))
    assert bot.get_chat_administrators.await_count == 1
    fake_clock.value = 601
    await cache.get(-1)
    assert bot.get_chat_administrators.await_count == 2
    await cache.refresh(-1)
    assert bot.get_chat_administrators.await_count == 3
    bot.get_chat_administrators.side_effect = RuntimeError("no access")
    with pytest.raises(RuntimeError):
        await cache.refresh(-1)
    assert -1 not in cache.entries


async def seed(sessions):
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Sinov"))
        session.add(User(id=1, first_name="Sinov"))


async def test_membership_refresh_during_fetch_cannot_restore_stale_admins():
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fetch(chat_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
            return [SimpleNamespace(user=SimpleNamespace(id=7))]
        return [SimpleNamespace(user=SimpleNamespace(id=8))]

    cache = AdminCache(SimpleNamespace(get_chat_administrators=fetch))
    first = asyncio.create_task(cache.get(-1))
    await started.wait()
    refreshed = asyncio.create_task(cache.refresh(-1))
    await asyncio.sleep(0)
    release.set()
    assert await first == {8}
    assert await refreshed == {8}
    assert calls == 2


async def test_pending_cache_startup_commit_and_resolution(sessions):
    await seed(sessions)
    pending = PendingChallenges()
    repo = ChallengeRepository(sessions, pending, ChatLocks())
    challenge = await repo.create(
        chat_id=-1, user_id=1, kind="text", prompt_key="test", deadline_at=utc_now()
    )
    assert pending.contains(-1, 1)
    loaded = PendingChallenges()
    await loaded.load(sessions)
    assert loaded.members == {(-1, 1)}
    assert await repo.resolve(-1, challenge, "done")
    assert not pending.contains(-1, 1)
    assert not await repo.resolve(-1, challenge, "missed")


async def test_game_repository_serializes_simultaneous_state_changes(sessions):
    await seed(sessions)
    repo = GameSessionRepository(sessions, ChatLocks())
    game = await repo.create(-1, game="quiz", started_by=1, state={"votes": 0})

    def vote(row):
        row.state["votes"] += 1

    await asyncio.gather(*[repo.change(-1, game, vote) for _ in range(25)])
    async with sessions() as session:
        assert (await session.get(GameSession, game)).state["votes"] == 25
    assert not await repo.change(-2, game, vote)


def test_metrics_rolling_minute_and_log(fake_clock, caplog):
    metrics = Metrics(clock=fake_clock.now)
    for _ in range(3):
        metrics.record_update()
    fake_clock.value = 59
    metrics.record_update()
    assert metrics.updates_per_minute == 4
    fake_clock.value = 60
    assert metrics.updates_per_minute == 1
    with caplog.at_level("INFO"):
        metrics.log(SimpleNamespace(queue_length=12), SimpleNamespace(last_tick_duration=0.025))
    assert "queue_length=12 updates_per_minute=1 last_tick_duration_ms=25.000" in caplog.text
