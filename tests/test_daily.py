from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from bot.db.models import Chat, Membership, PointEvent, ScheduledPost, User
from bot.services.content import ContentLibrary
from bot.services.daily import DailyService
from bot.services.participation import Participants
from bot.services.points import CheckinBuffer
from bot.services.scheduler import Scheduler
from bot.services.sender import Sender
from bot.utils.time import utc_now


@pytest.fixture
async def daily_app(sessions):
    async with sessions.begin() as session:
        session.add(
            Chat(
                id=-1,
                title="<Guruh & do‘stlar>",
                bot_is_admin=True,
                quiet_start=time(),
                quiet_end=time(),
                next_daily_at=utc_now() - timedelta(seconds=1),
            )
        )
        session.add(User(id=1, first_name="Sinov"))
        await session.flush()
        session.add(Membership(chat_id=-1, user_id=1, opted_in=True))
    participants = Participants()
    await participants.load(sessions)
    checkins = CheckinBuffer(sessions)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=100)))
    sender = Sender(sessions)
    daily = DailyService(sessions, bot, sender, ContentLibrary(), participants, checkins)
    try:
        yield daily, bot, checkins
    finally:
        await sender.close()


async def test_daily_tick_sends_once_and_restart_does_not_repost(sessions, daily_app):
    daily, bot, checkins = daily_app
    scheduler = Scheduler(sessions, hooks={"daily": daily.post})
    assert (await scheduler.tick())["daily"] == 1
    assert bot.send_message.await_count == 1
    assert "&lt;Guruh &amp; do‘stlar&gt;" in bot.send_message.await_args.args[1]
    async with sessions() as session:
        chat = await session.get(Chat, -1)
    await daily.post(chat, utc_now())
    restarted = DailyService(
        sessions, bot, daily.sender, daily.content, daily.participants, checkins
    )
    await restarted.load()
    await restarted.post(chat, utc_now())
    assert bot.send_message.await_count == 1
    async with sessions() as session:
        row = (await session.scalars(select(ScheduledPost))).one()
        assert row.status == "sent" and row.message_id == 100 and row.posted_at.tzinfo == UTC


async def test_checkin_is_memory_only_and_one_ledger_award_even_after_restart(sessions, daily_app):
    daily, bot, checkins = daily_app
    async with sessions() as session:
        chat = await session.get(Chat, -1)
    await daily.post(chat, utc_now())
    for message_id in range(101, 1101):
        daily.observe(
            SimpleNamespace(
                chat=SimpleNamespace(id=-1),
                from_user=SimpleNamespace(id=1),
                message_id=message_id,
                date=utc_now().replace(microsecond=0),
            )
        )
    assert len(checkins.pending) == 1
    await checkins.flush()
    restarted = DailyService(
        sessions, bot, daily.sender, daily.content, daily.participants, checkins
    )
    await restarted.load()
    restarted.observe(
        SimpleNamespace(
            chat=SimpleNamespace(id=-1),
            from_user=SimpleNamespace(id=1),
            message_id=1200,
            date=utc_now() + timedelta(seconds=1),
        )
    )
    await checkins.flush()
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 1
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 1


async def test_failed_send_is_auditable_and_not_retried_ambiguously(sessions, daily_app):
    daily, bot, checkins = daily_app
    bot.send_message.side_effect = RuntimeError("response lost")
    async with sessions() as session:
        chat = await session.get(Chat, -1)
    await daily.post(chat, utc_now())
    await daily.post(chat, utc_now())
    assert bot.send_message.await_count == 1
    async with sessions() as session:
        assert (await session.scalars(select(ScheduledPost))).one().status == "failed"


async def test_immediate_reply_before_send_response_is_not_lost(sessions, daily_app):
    daily, bot, checkins = daily_app
    async with sessions() as session:
        chat = await session.get(Chat, -1)

    async def send(*args, **kwargs):
        now = utc_now().replace(microsecond=0)
        daily.observe(
            SimpleNamespace(
                chat=SimpleNamespace(id=-1),
                from_user=SimpleNamespace(id=1),
                message_id=101,
                date=now,
            )
        )
        return SimpleNamespace(message_id=100, date=now)

    bot.send_message.side_effect = send
    await daily.post(chat, utc_now())
    assert len(checkins.pending) == 1


async def test_quiet_daily_is_deferred_not_dropped(sessions, daily_app):
    daily, bot, checkins = daily_app
    async with sessions.begin() as session:
        chat = await session.get(Chat, -1)
        chat.quiet_start, chat.quiet_end = time(23), time(8)
        chat.next_daily_at = datetime(2026, 11, 7, 19, tzinfo=UTC)
    scheduler = Scheduler(sessions, hooks={"daily": daily.post})
    await scheduler.tick(datetime(2026, 11, 7, 19, tzinfo=UTC))
    bot.send_message.assert_not_awaited()
    async with sessions() as session:
        assert (await session.get(Chat, -1)).next_daily_at == datetime(2026, 11, 8, 3, tzinfo=UTC)
