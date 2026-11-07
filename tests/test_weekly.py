import asyncio
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select, text
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import tg_user

from bot import texts
from bot.db.models import Challenge, Chat, PointEvent, ScheduledPost
from bot.services.schedule_times import next_weekly, stable_offset
from bot.services.weekly import Weekly, summary, weekly_period


@pytest.mark.parametrize("tz", ["Asia/Tashkent", "Europe/London", "America/New_York"])
def test_week_period_and_monday_deferral_preserve_sunday_identity(tz):
    chat = SimpleNamespace(id=-1, tz=tz)
    due = next_weekly(chat.id, tz, datetime(2026, 11, 7, 12, tzinfo=UTC))
    week, since, until = weekly_period(chat, due)
    assert week == date(2026, 11, 2)
    assert since.astimezone(ZoneInfo(tz)).hour == 0
    assert until.astimezone(ZoneInfo(tz)).date() == date(2026, 11, 9)
    monday_morning = datetime(2026, 11, 9, 8, tzinfo=ZoneInfo(tz)).astimezone(UTC)
    assert weekly_period(chat, monday_morning) == (week, since, until)


@pytest.fixture
async def weekly_app(game_app, sessions):
    feed, transport, runtime = game_app
    for user in range(1, 7):
        await runtime.groups.membership(-1, tg_user(user), opted_in=True)
    due = next_weekly(-1, "Asia/Tashkent", datetime(2026, 11, 7, 12, tzinfo=UTC))
    async with sessions.begin() as session:
        chat = await session.get(Chat, -1)
        chat.next_weekly_at = due
        chat.next_daily_at = chat.next_challenge_at = None
        chat.quiet_start = chat.quiet_end = time()
        week, since, until = weekly_period(chat, due)
        for user in range(1, 7):
            session.add(
                PointEvent(
                    chat_id=-1,
                    user_id=user,
                    delta=user * 10,
                    reason="test",
                    ref_id=f"seed:{user}",
                    created_at=since + timedelta(days=1),
                )
            )
        for index in range(3):
            session.add(
                PointEvent(
                    chat_id=-1,
                    user_id=2,
                    delta=3,
                    reason="quiz",
                    ref_id=f"quiz:{index}",
                    created_at=since + timedelta(days=1),
                )
            )
        for reason, delta in (("mafia_win", 10), ("mafia_survived", 3)):
            session.add(
                PointEvent(
                    chat_id=-1,
                    user_id=2,
                    delta=delta,
                    reason=reason,
                    ref_id="game:one",
                    created_at=since + timedelta(days=1),
                )
            )
        session.add_all(
            [
                PointEvent(
                    chat_id=-1,
                    user_id=1,
                    delta=9999,
                    reason="old",
                    ref_id="old",
                    created_at=since - timedelta(days=1),
                ),
                PointEvent(
                    chat_id=-1,
                    user_id=1,
                    delta=5000,
                    reason="future",
                    ref_id="future",
                    created_at=until + timedelta(minutes=1),
                ),
                Challenge(
                    chat_id=-1,
                    user_id=1,
                    kind="text",
                    prompt_key="x",
                    status="done",
                    created_at=since,
                    deadline_at=due,
                    resolved_at=since + timedelta(days=1),
                ),
                Challenge(
                    chat_id=-1,
                    user_id=3,
                    kind="voice",
                    prompt_key="y",
                    status="missed",
                    created_at=since,
                    deadline_at=due,
                    resolved_at=since + timedelta(days=1),
                ),
                Challenge(
                    chat_id=-1,
                    user_id=6,
                    kind="photo",
                    prompt_key="z",
                    status="pending",
                    created_at=since,
                    deadline_at=due + timedelta(hours=1),
                ),
            ]
        )
    return feed, transport, runtime, due


async def test_summary_top_five_distinct_scored_activity_and_challenge_window(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    chat = await runtime.groups.get(-1)
    _, since, until = weekly_period(chat, due)
    async with sessions() as session:
        data = await summary(session, -1, since, until)
    assert [row.id for row in data["top"]] == [6, 5, 2, 4, 3]
    assert data["active"].id == 2 and data["active"].activities == 5
    assert (data["done"], data["missed"], data["pending"]) == (1, 1, 1)


async def test_weekly_tick_posts_once_with_footer_button_and_restart_safety(
    weekly_app, sessions, settings
):
    feed, transport, runtime, due = weekly_app
    counts = await runtime.scheduler.tick(due)
    assert counts["weekly"] == 1
    sent = transport.methods[-1]
    assert isinstance(sent, SendMessage)
    assert "Haftalik oqibat" in sent.text and "&lt;Sinov&gt;" in sent.text
    assert texts.SLOGAN in sent.text and "Muallif: @oqibat.test" in sent.text
    assert sent.reply_markup.inline_keyboard[0][0].url.startswith(
        "https://t.me/OqibatBot?startgroup=add"
    )
    before = len(transport.methods)
    assert (await runtime.scheduler.tick(due))["weekly"] == 0
    restarted = Weekly(
        sessions, runtime.locks, runtime.game_hub.bot, runtime.sender, runtime.checkins, settings
    )
    await restarted.post(await runtime.groups.get(-1), due)
    assert len(transport.methods) == before
    async with sessions() as session:
        post = (
            await session.scalars(select(ScheduledPost).where(ScheduledPost.kind == "weekly"))
        ).one()
        assert post.local_date == date(2026, 11, 2) and post.status == "sent"


async def test_concurrent_weekly_calls_send_once(weekly_app):
    feed, transport, runtime, due = weekly_app
    chat = await runtime.groups.get(-1)
    before = len(transport.methods)
    await asyncio.gather(runtime.weekly.post(chat, due), runtime.weekly.post(chat, due))
    assert len(transport.methods) == before + 1


async def test_quiet_monday_deferral_and_next_sunday_are_two_different_weeks(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    async with sessions.begin() as session:
        chat = await session.get(Chat, -1)
        chat.quiet_start, chat.quiet_end = time(19), time(8)
    before = len(transport.methods)
    await runtime.scheduler.tick(due)
    assert len(transport.methods) == before
    monday = datetime(2026, 11, 9, 3, tzinfo=UTC)
    assert (await runtime.groups.get(-1)).next_weekly_at == monday
    await runtime.scheduler.tick(monday)
    following = (await runtime.groups.get(-1)).next_weekly_at
    assert following.astimezone(ZoneInfo("Asia/Tashkent")).date() == date(2026, 11, 15)
    async with sessions.begin() as session:
        chat = await session.get(Chat, -1)
        chat.quiet_start = chat.quiet_end = time()
    await runtime.scheduler.tick(following)
    async with sessions() as session:
        weeks = (
            await session.scalars(
                select(ScheduledPost.local_date)
                .where(ScheduledPost.kind == "weekly")
                .order_by(ScheduledPost.local_date)
            )
        ).all()
    assert weeks == [date(2026, 11, 2), date(2026, 11, 9)]


async def test_failed_weekly_is_audited_backs_off_and_is_not_replayed(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    with patch.object(runtime.sender, "send", return_value=None):
        await runtime.scheduler.tick(due)
    chat = await runtime.groups.get(-1)
    assert chat.next_weekly_at == due + timedelta(minutes=10)
    before = len(transport.methods)
    await runtime.scheduler.tick(chat.next_weekly_at)
    assert len(transport.methods) == before
    async with sessions() as session:
        post = (
            await session.scalars(select(ScheduledPost).where(ScheduledPost.kind == "weekly"))
        ).one()
        assert post.status == "failed"


async def test_all_group_help_commands_footer_and_private_help(weekly_app):
    feed, transport, runtime, due = weekly_app
    await feed(command_update("/help"))
    sent = transport.methods[-1]
    assert all(f"/{command}" in sent.text for command in texts.GROUP_COMMANDS)
    assert "Muallif: @oqibat.test" in sent.text
    assert "startgroup=add" in sent.reply_markup.inline_keyboard[0][0].url
    assert len(texts.help_text("oqibat.test")) < 4096


async def test_empty_week_and_query_index(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    async with sessions() as session:
        data = await summary(session, -1, due + timedelta(days=30), due + timedelta(days=31))
        plan = (
            await session.execute(
                text(
                    "EXPLAIN QUERY PLAN SELECT SUM(delta) FROM point_events "
                    "WHERE chat_id=-1 AND created_at >= '2026-11-01'"
                )
            )
        ).all()
    assert not data["top"] and data["active"] is None
    assert "ix_point_events_chat_created" in str(plan)


async def test_migrated_chat_keeps_week_identity_when_hash_offset_changes(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    destination = next(
        -1000000 - i
        for i in range(10000)
        if stable_offset(-1000000 - i, "weekly") > stable_offset(-1, "weekly")
    )
    await runtime.migrations.migrate(-1, destination)
    chat = await runtime.groups.get(destination)
    await runtime.weekly.post(chat, due)
    async with sessions() as session:
        post = (
            await session.scalars(select(ScheduledPost).where(ScheduledPost.kind == "weekly"))
        ).one()
        assert post.chat_id == destination and post.local_date == date(2026, 11, 2)
