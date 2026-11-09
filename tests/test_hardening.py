import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select
from test_challenge_flows import challenge_app as challenge_app
from test_challenge_flows import command_update, video_update
from test_easy_games import game_app as game_app
from test_group_flows import callback
from test_group_flows import group_app as group_app
from test_private_and_startup import update_for

from bot import texts
from bot.db.models import Challenge, GameSession, Membership, PointEvent, ScheduledPost, User
from bot.handlers.owner import erase_confirm
from bot.services.recovery import Recovery, fresh
from bot.services.sender import Sender
from bot.utils.time import utc_now


def test_six_hour_boundary_and_future_events():
    now = utc_now()
    assert fresh(now - timedelta(hours=6), now)
    assert not fresh(now - timedelta(hours=6, microseconds=1), now)
    assert not fresh(now + timedelta(seconds=1), now)


async def test_crash_after_completion_before_send_recovers_without_points(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    key = runtime.pending.for_chat(-1)[0]
    await runtime.challenges.complete(-1, key, 1, "video_note", utc_now(), 200)
    async with sessions() as session:
        assert (await session.get(Challenge, key)).result_announced_at is None
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 15
    # New orchestrator models restart; only the committed business row is needed.
    recovery = Recovery(runtime, runtime.game_hub.bot, None)
    before = len(transport.methods)
    await recovery.tick()
    await recovery.tick()
    assert len(transport.methods) == before + 1
    async with sessions() as session:
        assert (await session.get(Challenge, key)).result_announced_at
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 15
        assert await session.scalar(select(func.count()).select_from(Challenge)) == 1


async def test_pending_assignment_and_stale_results_are_recovered_or_skipped(
    challenge_app, sessions
):
    feed, transport, runtime = challenge_app
    now = utc_now()
    created = await runtime.challenges.assign(
        -1, now, runtime.content.banks["challenges"], "photo", True
    )
    key = created[0].id
    await runtime.recovery.tick(now + timedelta(seconds=1))
    async with sessions() as session:
        assert (await session.get(Challenge, key)).assigned_announced_at
    # State/points commit, then process disappears before notification.
    await runtime.challenges.complete(-1, key, 1, "photo", now + timedelta(seconds=2), 999)
    before = len(transport.methods)
    await runtime.recovery.tick(now + timedelta(hours=7))
    await runtime.recovery.tick(now + timedelta(hours=8))
    assert len(transport.methods) == before
    async with sessions() as session:
        assert (await session.get(Challenge, key)).result_skipped_at
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 10


async def test_pending_result_is_not_prematurely_skipped(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    key = runtime.pending.for_chat(-1)[0]
    await runtime.recovery.tick()
    async with sessions() as session:
        assert (await session.get(Challenge, key)).result_skipped_at is None
    await feed(video_update(999))
    async with sessions() as session:
        assert (await session.get(Challenge, key)).result_announced_at


async def test_old_reserved_post_is_skipped_without_send(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    now = utc_now()
    async with sessions.begin() as session:
        session.add(
            ScheduledPost(
                chat_id=-1, kind="daily", local_date=now.date(), claimed_at=now - timedelta(hours=7)
            )
        )
    before = len(transport.methods)
    await runtime.recovery.tick(now)
    async with sessions() as session:
        row = (await session.scalars(select(ScheduledPost))).one()
        assert row.status == "skipped" and row.sent_at is None
    assert len(transport.methods) == before


async def test_private_owner_stats_permissions_and_privacy(game_app):
    feed, transport, runtime = game_app
    await feed(update_for("/stats"))  # user 42, configured owner 123
    assert transport.methods[-1].text == texts.OWNER_ONLY
    request = update_for("/stats")
    request = request.model_copy(
        update={
            "message": request.message.model_copy(
                update={"from_user": request.message.from_user.model_copy(update={"id": 123})}
            )
        }
    )
    await feed(request)
    assert "Faol guruhlar: 1" in transport.methods[-1].text
    await feed(command_update("/maxfiylik"))
    assert transport.methods[-1].text == texts.PRIVACY


async def test_confirmed_erasure_removes_rows_game_json_and_pending_buffers(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/duel"))
    old_game = runtime.game_cache.for_chat(-1)[0]
    await runtime.points.award(-1, 2, 2, "duel_win", f"game:{old_game.id}")
    runtime.activity.observe(-1, 1, "Private old name", "old")
    runtime.checkins.add(-1, 1, utc_now().date())
    await runtime.points.award(-1, 1, 3, "test", "one")
    token = runtime.owner_tools.confirm(1)
    assert not await runtime.owner_tools.erase(2, token)
    assert await runtime.owner_tools.erase(1, token)
    assert not await runtime.owner_tools.erase(1, token)
    await runtime.activity.flush()
    await runtime.checkins.flush()
    await runtime.effects.drain()
    async with sessions() as session:
        assert await session.get(User, 1) is None
        for model in (Membership, Challenge, PointEvent):
            assert not (await session.scalars(select(model).where(model.user_id == 1))).all()
        game = (await session.scalars(select(GameSession))).one()
        assert game.started_by == 0 and game.state == {"erased": True}
        assert game.status == "cancelled"
        assert await session.get(User, 2) is not None
    assert not runtime.participants.contains(-1, 1)
    assert not runtime.game_cache.for_chat(-1)
    await feed(command_update("/duel", user_id=2))
    new_game = runtime.game_cache.for_chat(-1)[0]
    assert new_game.id > old_game.id
    assert await runtime.points.award(-1, 2, 2, "duel_win", f"game:{new_game.id}")
    assert (await runtime.points.stats(-1, 2))[0] == 4


async def test_recovery_failure_backs_off_ten_minutes(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    now = utc_now()
    await runtime.challenges.assign(-1, now, runtime.content.banks["challenges"], "photo", True)
    with patch.object(runtime.sender, "send", return_value=None):
        await runtime.recovery.tick(now)
    before = len(transport.methods)
    await runtime.recovery.tick(now + timedelta(minutes=9))
    assert len(transport.methods) == before
    await runtime.recovery.tick(now + timedelta(minutes=10))
    assert len(transport.methods) == before + 1


async def test_recovered_miss_does_not_reapply_moderation_or_points(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    await runtime.challenge_service.assign(-1, "photo", force=True)
    key = runtime.pending.for_chat(-1)[0]
    async with sessions() as session:
        deadline = (await session.get(Challenge, key)).deadline_at
    await runtime.challenges.expire(-1, key, deadline)
    with patch.object(runtime.penalties, "apply") as moderation:
        await runtime.recovery.tick(deadline + timedelta(seconds=1))
        await runtime.recovery.tick(deadline + timedelta(seconds=2))
    moderation.assert_not_called()
    assert (await runtime.points.stats(-1, 1))[0] == -5


async def test_erasure_foreign_private_callback_is_rejected_without_db(game_app):
    feed, transport, runtime = game_app
    tools = SimpleNamespace(erase=AsyncMock())
    query = SimpleNamespace(
        id="q",
        data="erase:x",
        from_user=SimpleNamespace(id=1),
        message=SimpleNamespace(chat=SimpleNamespace(type="private", id=2)),
    )
    sender = SimpleNamespace(answer_callback_query=AsyncMock())
    await erase_confirm(query, runtime.game_hub.bot, sender, tools)
    tools.erase.assert_not_awaited()
    assert sender.answer_callback_query.call_args.kwargs["show_alert"]


async def test_erased_user_old_messages_and_join_buttons_cannot_restore_data(game_app, sessions):
    feed, transport, runtime = game_app
    assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    await feed(video_update(user=1))
    await feed(callback("join", user=1))
    await runtime.activity.flush()
    async with sessions() as session:
        assert await session.get(User, 1) is None
    request = update_for("/start")
    request = request.model_copy(
        update={
            "message": request.message.model_copy(
                update={
                    "from_user": request.message.from_user.model_copy(update={"id": 1}),
                    "chat": request.message.chat.model_copy(update={"id": 1}),
                }
            )
        }
    )
    await feed(request)
    await runtime.activity.flush()
    async with sessions() as session:
        assert await session.get(User, 1) is not None
        assert await session.get(Membership, (-1, 1)) is None


async def test_drain_finishes_accepted_work_even_when_caller_cancelled(sessions):
    sender = Sender(sessions)
    started, finish = asyncio.Event(), asyncio.Event()

    async def operation():
        started.set()
        await finish.wait()
        return 42

    request = asyncio.create_task(sender.send(-1, operation))
    await started.wait()
    request.cancel()
    await asyncio.gather(request, return_exceptions=True)
    drain = asyncio.create_task(sender.drain(1))
    finish.set()
    await drain
    assert not sender._active and sender.queue_length == 0
    assert await sender.send(-1, operation) is None
    await sender.close()


async def test_drain_timeout_is_bounded(sessions):
    sender = Sender(sessions)
    blocked = asyncio.Event()
    request = asyncio.create_task(sender.send(-1, blocked.wait))
    await asyncio.sleep(0)
    await sender.drain(0.01)
    await sender.close()
    await asyncio.gather(request, return_exceptions=True)
