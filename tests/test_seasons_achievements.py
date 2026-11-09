from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from aiogram.methods import SendPhoto
from sqlalchemy import func, select
from test_challenge_flows import challenge_app as challenge_app
from test_challenge_flows import command_update, video_update
from test_easy_games import game_app as game_app
from test_group_flows import group_app as group_app
from test_result_cards import photo_transport

from bot.db.models import Achievement, Chat, PointEvent, ScheduledPost
from bot.services.achievements import longest_streak, streak_length
from bot.services.schedule_times import stable_offset
from bot.services.seasons import month_bounds, next_season
from bot.services.sender import Priority
from bot.utils.time import utc_now


@pytest.mark.parametrize(
    "tz,at,expected",
    [
        ("Asia/Tashkent", datetime(2027, 1, 1, tzinfo=UTC), datetime(2026, 12, 31, 19, tzinfo=UTC)),
        (
            "America/New_York",
            datetime(2026, 11, 15, tzinfo=UTC),
            datetime(2026, 11, 1, 4, tzinfo=UTC),
        ),
        (
            "Asia/Tashkent",
            datetime(2026, 2, 28, 20, tzinfo=UTC),
            datetime(2026, 2, 28, 19, tzinfo=UTC),
        ),
    ],
)
def test_calendar_months_utc_boundaries(tz, at, expected):
    since, until = month_bounds(at, tz)
    assert since == expected and since <= at < until
    assert since.tzinfo == UTC and until.tzinfo == UTC


def test_streak_pure_gaps_duplicates_and_month_crossing():
    with pytest.raises(ValueError):
        month_bounds(datetime(2026, 1, 1), "Asia/Tashkent")
    start = date(2026, 1, 28)
    days = [start + timedelta(days=n) for n in range(7)]
    assert streak_length(days + days, days[-1]) == longest_streak(days) == 7
    assert streak_length(days, days[-1] + timedelta(days=1)) == 0
    assert longest_streak(days[:3] + days[4:]) == 3
    after = datetime(2026, 12, 31, 23, tzinfo=UTC)
    due = next_season(-123, "Asia/Tashkent", after)
    assert due == datetime(2027, 1, 1, 4, tzinfo=UTC) + timedelta(
        seconds=stable_offset(-123, "season")
    )


async def test_atomic_streak_thresholds_idempotency_and_reset(game_app, sessions):
    feed, transport, runtime = game_app
    start = date(2026, 1, 28)
    for day in range(30):
        runtime.checkins.add(-1, 1, start + timedelta(days=day))
    await runtime.checkins.flush()
    for day in range(31):
        runtime.checkins.add(-1, 1, start + timedelta(days=day))
    await runtime.checkins.flush()
    assert (await runtime.points.stats(-1, 1))[0] == 44  # 31 + 3 + 10
    for day in range(33, 40):
        runtime.checkins.add(-1, 1, start + timedelta(days=day))
    await runtime.checkins.flush()
    assert (await runtime.points.stats(-1, 1))[0] == 54
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Achievement)) == 2
        assert (
            await session.scalar(
                select(func.count())
                .select_from(PointEvent)
                .where(PointEvent.reason == "streak_bonus")
            )
            == 3
        )


async def test_streak_transaction_rolls_back_base_bonus_and_unlock(game_app, sessions):
    feed, transport, runtime = game_app
    for day in range(7):
        runtime.checkins.add(-1, 1, date(2026, 1, 1) + timedelta(days=day))
    with patch("bot.services.achievements.unlock", side_effect=RuntimeError("test")):
        with pytest.raises(RuntimeError):
            await runtime.checkins.flush()
    assert (await runtime.points.stats(-1, 1))[0] == 0
    assert len(runtime.checkins.pending) == 7
    await runtime.checkins.flush()
    assert (await runtime.points.stats(-1, 1))[0] == 10


async def test_task_video_milestones_unlock_once(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    await feed(video_update(999))
    await feed(video_update(1000))
    rows = await runtime.achievements.list(-1, 1, reconcile=True)
    assert {row.key for row in rows} == {"first_task", "first_video"}
    assert (await runtime.points.stats(-1, 1))[0] == 15


async def test_krok_mafia_and_batched_low_priority_announcements(game_app, sessions):
    feed, transport, runtime = game_app
    await runtime.groups.change_setting(-1, "quiet_start", time())
    await runtime.groups.change_setting(-1, "quiet_end", time())
    for index in range(10):
        await runtime.points.award(-1, 1, 5, "krokodil", f"word:{index}")
    await runtime.points.award(-1, 1, 10, "mafia_win", "game:100")
    assert not await runtime.points.award(-1, 1, 10, "mafia_win", "game:100")
    with patch.object(runtime.sender, "send", wraps=runtime.sender.send) as sender:
        await runtime.achievements.announce(utc_now())
        assert sender.call_args.kwargs["priority"] == Priority.BULK
    before = len(transport.methods)
    await runtime.achievements.announce(utc_now())
    assert len(transport.methods) == before
    async with sessions() as session:
        rows = (await session.scalars(select(Achievement))).all()
        assert {row.key for row in rows} == {"ten_krok", "first_mafia_win"}
        assert all(row.claimed_at and row.announced_at for row in rows)


async def test_season_card_is_prior_month_once_and_never_resets_points(game_app, sessions):
    feed, transport, runtime = game_app
    runtime.cards.enabled = True
    due = datetime(2026, 12, 1, 4, tzinfo=UTC) + timedelta(seconds=stable_offset(-1, "season"))
    async with sessions.begin() as session:
        chat = await session.get(Chat, -1)
        chat.next_season_at, chat.quiet_start, chat.quiet_end = due, time(), time()
        session.add_all(
            [
                PointEvent(
                    chat_id=-1,
                    user_id=1,
                    delta=10,
                    reason="seed",
                    ref_id="old",
                    created_at=datetime(2026, 11, 15, tzinfo=UTC),
                ),
                PointEvent(
                    chat_id=-1, user_id=1, delta=5, reason="seed", ref_id="new", created_at=due
                ),
            ]
        )
    runtime.scheduler.hooks = {"season": runtime.seasons.post}
    with patch.object(transport, "make_request", side_effect=photo_transport(transport)):
        assert (await runtime.scheduler.tick(due))["season"] == 1
        await runtime.scheduler.tick(due)
        await runtime.recovery.tick(due)
    photos = [item for item in transport.methods if isinstance(item, SendPhoto)]
    assert len(photos) == 1 and "10 ball" in photos[0].caption
    assert "5 ball" not in photos[0].caption
    async with sessions() as session:
        post = (
            await session.scalars(select(ScheduledPost).where(ScheduledPost.kind == "season"))
        ).one()
        assert post.local_date == date(2026, 11, 1) and post.sent_at
    assert (await runtime.points.stats(-1, 1))[0] == 15


async def test_top_uses_season_and_alltime_and_erasure_removes_achievements(game_app, sessions):
    feed, transport, runtime = game_app
    now = datetime(2026, 12, 15, tzinfo=UTC)
    async with sessions.begin() as session:
        session.add_all(
            [
                PointEvent(
                    chat_id=-1,
                    user_id=1,
                    delta=100,
                    reason="test",
                    ref_id="nov",
                    created_at=datetime(2026, 11, 15, tzinfo=UTC),
                ),
                PointEvent(
                    chat_id=-1, user_id=1, delta=3, reason="test", ref_id="dec", created_at=now
                ),
            ]
        )
    with patch("bot.handlers.stats.utc_now", return_value=now):
        await feed(command_update("/top"))
    text = transport.methods[-1].text
    assert "Joriy mavsum" in text and "3 ball" in text and "103 ball" in text
    await runtime.points.award(-1, 1, 10, "mafia_win", "game:999")
    await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    async with sessions() as session:
        assert not (await session.scalars(select(Achievement))).all()
