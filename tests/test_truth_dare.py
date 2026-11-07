import asyncio
from datetime import time, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import EditMessageText
from aiogram.types import Update
from sqlalchemy import func, select
from test_challenge_flows import command_update, video_update
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user

from bot import texts
from bot.db.models import Challenge, GameSession, PointEvent
from bot.games.truth_dare import can_answer
from bot.utils.time import utc_now


@pytest.fixture
async def hyj_app(game_app):
    feed, transport, runtime = game_app
    await runtime.groups.change_setting(-1, "quiet_start", time())
    await runtime.groups.change_setting(-1, "quiet_end", time())
    return game_app


def targeted_command(target=2):
    update = command_update("/hyj")
    reply = command_update("Hi", 5, target).message
    return update.model_copy(
        update={"message": update.message.model_copy(update={"reply_to_message": reply})}
    )


def media(kind, user=2, message_id=500):
    if kind in {"voice", "video_note"}:
        return video_update(message_id, user, kind)
    update = command_update("Mening javobim", message_id, user)
    if kind == "photo":
        payload = update.model_dump()
        payload["message"].update(
            text=None,
            entities=[],
            photo=[{"file_id": "test", "file_unique_id": "test", "width": 100, "height": 100}],
        )
        return Update.model_validate(payload)
    return update


def test_truth_validation_target_kind_time_and_message_boundary():
    now = utc_now()
    state = {
        "phase": "truth",
        "target": 2,
        "answer_after_id": 100,
        "answer_from": now.isoformat(),
        "answer_until": (now + timedelta(minutes=30)).isoformat(),
    }
    for kind in ("voice", "text"):
        assert can_answer(state, 2, kind, now, 101)
    assert not can_answer(state, 1, "text", now, 101)
    assert not can_answer(state, 2, "photo", now, 101)
    assert not can_answer(state, 2, "text", now, 100)
    assert not can_answer(state, 2, "text", now - timedelta(seconds=1), 101)
    assert not can_answer(state, 2, "text", now + timedelta(minutes=31), 101)
    assert not can_answer({"phase": "choice"}, 2, "text", now, 101)


@pytest.mark.parametrize("kind", ["text", "voice"])
async def test_truth_target_only_text_or_voice_awards_five_once(hyj_app, kind):
    feed, transport, runtime = hyj_app
    runtime.content.banks["truth_questions"] = [{"key": "truth_test", "text": "<Savol> & javob?"}]
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"ht:{game.id}", 3))
    assert transport.methods[-1].text == texts.HYJ_TARGET_ONLY
    assert runtime.game_cache.main(-1).state["phase"] == "choice"
    await feed(callback(f"ht:{game.id}", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.main(-1)
    assert game.state["phase"] == "truth"
    assert "&lt;Savol&gt; &amp; javob?" in transport.methods[-1].text
    await feed(media(kind, user=3))
    assert runtime.game_cache.main(-1)
    await feed(media(kind))
    await feed(media(kind))
    assert runtime.game_cache.main(-1) is None
    assert (await runtime.points.stats(-1, 2))[0] == 5


@pytest.mark.parametrize(
    "kind,points", [("video_note", 15), ("voice", 10), ("photo", 10), ("text", 5)]
)
async def test_dare_reuses_challenge_engine_one_hour_and_kind_points(
    hyj_app, sessions, kind, points
):
    feed, transport, runtime = hyj_app
    runtime.content.banks["challenges"] = [
        {"key": "dare_test", "kind": kind, "text": "Sinov vazifasi"}
    ]
    await feed(targeted_command())
    game_id = runtime.game_cache.main(-1).id
    await feed(callback(f"hd:{game_id}", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.main(-1)
    assert game.state["phase"] == "dare"
    async with sessions() as session:
        challenge = (await session.scalars(select(Challenge))).one()
        assert challenge.game_session_id == game_id and challenge.user_id == 2
        assert challenge.deadline_at - challenge.created_at == timedelta(hours=1)
    await feed(media(kind))
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    assert not runtime.pending.for_chat(-1)
    assert (await runtime.points.stats(-1, 2))[0] == points
    async with sessions() as session:
        assert (await session.get(GameSession, game_id)).status == "finished"


@pytest.mark.parametrize("mode", ["mute", "kick"])
async def test_refusal_cancels_dare_only_minus_two_and_never_moderates(hyj_app, sessions, mode):
    feed, transport, runtime = hyj_app
    await runtime.groups.change_setting(-1, "penalty_mode", mode)
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    with patch.object(runtime.penalties, "apply", new=AsyncMock()) as moderate:
        await feed(callback(f"hr:{game.id}", 2))
        await feed(callback(f"hr:{game.id}", 2))
        await runtime.effects.drain()
        await runtime.scheduler.deadline_tick(utc_now() + timedelta(days=2))
        moderate.assert_not_awaited()
    assert (await runtime.points.stats(-1, 2))[0] == -2
    async with sessions() as session:
        assert (await session.scalars(select(Challenge))).one().status == "cancelled"
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 1


async def test_refusal_before_choice_and_race_with_completion_are_atomic(hyj_app, sessions):
    feed, transport, runtime = hyj_app
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hr:{game.id}", 2))
    await runtime.effects.drain()
    assert (await runtime.points.stats(-1, 2))[0] == -2
    runtime.content.banks["challenges"] = [
        {"key": "dare_test", "kind": "video_note", "text": "Video"}
    ]
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    await asyncio.gather(feed(media("video_note")), feed(callback(f"hr:{game.id}", 2)))
    await runtime.effects.drain()
    assert (await runtime.points.stats(-1, 2))[0] in {-4, 13}
    async with sessions() as session:
        challenge = (await session.scalars(select(Challenge))).one()
        assert challenge.status in {"done", "cancelled"}
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 2


async def test_stop_cancels_pending_dare_without_points_and_truth_times_out(hyj_app, sessions):
    feed, transport, runtime = hyj_app
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    await feed(command_update("/stop"))
    await runtime.effects.drain()
    assert not runtime.pending.for_chat(-1)
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"ht:{game.id}", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.main(-1)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
    assert runtime.game_cache.main(-1) is None


async def test_random_target_and_existing_challenge_dare_conflict(hyj_app):
    feed, transport, runtime = hyj_app
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    await feed(command_update("/hyj"))
    game = runtime.game_cache.main(-1)
    target = game.state["target"]
    assert target in runtime.participants.for_chat(-1)
    await feed(callback(f"hd:{game.id}", target))
    assert transport.methods[-1].text == texts.PENDING_CHALLENGE
    assert runtime.game_cache.main(-1).state["phase"] == "choice"
    await runtime.groups.membership(-1, tg_user(target), opted_in=False)
    await feed(callback(f"ht:{game.id}", target))
    assert transport.methods[-1].text == texts.HYJ_TARGET_ONLY


async def test_refusal_race_with_expiry_records_only_one_outcome(hyj_app, sessions):
    feed, transport, runtime = hyj_app
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    async with sessions() as session:
        challenge = (await session.scalars(select(Challenge))).one()
    await asyncio.gather(
        runtime.challenge_service.expire(challenge, challenge.deadline_at),
        feed(callback(f"hr:{game.id}", 2)),
    )
    await runtime.effects.drain()
    assert (await runtime.points.stats(-1, 2))[0] in {-2, -5}
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 1
        assert (await session.get(GameSession, game.id)).status == "finished"


async def test_failed_refusal_transaction_rolls_back_task_game_and_points(hyj_app, sessions):
    feed, transport, runtime = hyj_app
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    with patch("bot.db.repo.games.record_event", new=AsyncMock(side_effect=RuntimeError("db"))):
        with pytest.raises(RuntimeError):
            await runtime.games.refuse_hyj(-1, game.id, 2)
    async with sessions() as session:
        assert (await session.scalars(select(Challenge))).one().status == "pending"
        assert (await session.get(GameSession, game.id)).status == "running"
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
    assert runtime.pending.for_chat(-1)


async def test_target_optout_cancels_linked_game_and_dare_without_penalty(hyj_app, sessions):
    feed, transport, runtime = hyj_app
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", 2))
    await runtime.effects.drain()
    await runtime.groups.membership(-1, tg_user(2), opted_in=False)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    assert not runtime.pending.for_chat(-1)
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).status == "cancelled"
        assert (await session.scalars(select(Challenge))).one().status == "cancelled"
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_slow_truth_edit_cannot_overwrite_refusal_result(hyj_app):
    feed, transport, runtime = hyj_app
    runtime.content.banks["truth_questions"] = [{"key": "truth_test", "text": "Maxsus savol"}]
    await feed(targeted_command())
    game = runtime.game_cache.main(-1)
    original = transport.make_request
    started, release = asyncio.Event(), asyncio.Event()
    applied = []

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, EditMessageText) and "Maxsus savol" in method.text:
            started.set()
            await release.wait()
        result = await original(bot, method, timeout)
        if isinstance(method, EditMessageText):
            applied.append(method.text)
        return result

    with patch.object(transport, "make_request", side_effect=request):
        await feed(callback(f"ht:{game.id}", 2))
        await asyncio.wait_for(started.wait(), 2)
        try:
            await asyncio.wait_for(feed(callback(f"hr:{game.id}", 2)), 2)
            assert runtime.game_cache.main(-1) is None
        finally:
            release.set()
        await runtime.effects.drain()
    assert "rad etdi" in applied[-1]
    assert (await runtime.points.stats(-1, 2))[0] == -2
