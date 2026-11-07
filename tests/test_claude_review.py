import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramMigrateToChat
from aiogram.methods import GetChatMember, SendMessage
from aiogram.types import Update
from sqlalchemy import func, select
from test_challenge_flows import command_update, video_update
from test_group_flows import bot_update, callback, tg_user
from test_group_flows import group_app as group_app

from bot import texts
from bot.db.models import (
    Challenge,
    Chat,
    ContentUsage,
    GameSession,
    Membership,
    PointEvent,
    ScheduledPost,
)
from bot.db.repo.migrations import CHILDREN
from bot.services.scheduler import Scheduler
from bot.utils.time import utc_now

NEW = -1001234567890


async def seed(runtime, sessions):
    await runtime.groups.membership(-1, tg_user(1), opted_in=True)
    now = utc_now()
    async with sessions.begin() as session:
        session.add_all(
            [
                PointEvent(chat_id=-1, user_id=1, delta=15, reason="test", ref_id="a"),
                ContentUsage(chat_id=-1, content_key="sample", used_at=now),
                ScheduledPost(
                    chat_id=-1,
                    kind="daily",
                    local_date=now.date(),
                    status="sent",
                    message_id=999,
                    posted_at=now - timedelta(seconds=5),
                ),
                Challenge(
                    chat_id=-1,
                    user_id=1,
                    kind="video_note",
                    prompt_key="sample",
                    message_id=999,
                    created_at=now - timedelta(seconds=5),
                    deadline_at=now + timedelta(hours=1),
                ),
                GameSession(
                    chat_id=-1,
                    game="quiz",
                    started_by=1,
                    state={"board_id": 999},
                    phase_deadline_at=now + timedelta(minutes=1),
                ),
            ]
        )
    await runtime.pending.load(sessions)
    await runtime.daily.load()


async def test_migration_moves_every_table_and_caches_and_survives_restart(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await seed(runtime, sessions)
    await runtime.migrations.migrate(-1, NEW)
    await runtime.migrations.migrate(-1, NEW)  # duplicate Telegram service update
    async with sessions() as session:
        old, new = await session.get(Chat, -1), await session.get(Chat, NEW)
        assert not old.is_active and old.next_daily_at is None
        assert old.migrated_to_chat_id == NEW and new.bot_is_admin
        for model in CHILDREN:
            assert (
                await session.scalar(
                    select(func.count()).select_from(model).where(model.chat_id == -1)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(model).where(model.chat_id == NEW)
                )
                == 1
            )
        challenge = (await session.scalars(select(Challenge))).one()
        assert challenge.message_id == 999 and challenge.origin_chat_id == -1
        assert (await session.scalars(select(GameSession))).one().state["board_id"] is None
    assert runtime.pending.contains(NEW, 1) and not runtime.pending.contains(-1, 1)
    assert runtime.participants.contains(NEW, 1)
    assert runtime.daily.posts[NEW][1] == 0
    await runtime.migrations.load()
    assert runtime.migrations.resolve(-1) == NEW
    await runtime.pending.load(sessions)
    # Message IDs restart in the supergroup: low IDs must still complete an older task.
    update = video_update(2)
    update = update.model_copy(
        update={
            "message": update.message.model_copy(
                update={
                    "chat": update.message.chat.model_copy(update={"id": NEW, "type": "supergroup"})
                }
            )
        }
    )
    await feed(update)
    assert (await runtime.points.stats(NEW, 1))[0] == 30


async def test_migration_rolls_back_all_rows_and_aliases_on_failure(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await seed(runtime, sessions)
    with patch("bot.db.repo.migrations.snapshot", new=AsyncMock(side_effect=RuntimeError("fail"))):
        with pytest.raises(RuntimeError):
            await runtime.migrations.migrate(-1, NEW)
    assert runtime.migrations.resolve(-1) == -1
    async with sessions() as session:
        assert await session.get(Chat, NEW) is None
        assert (await session.get(Chat, -1)).is_active
        for model in CHILDREN:
            assert (
                await session.scalar(
                    select(func.count()).select_from(model).where(model.chat_id == -1)
                )
                == 1
            )


async def test_migration_merges_stub_without_restoring_optout_or_double_points(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await seed(runtime, sessions)
    async with sessions.begin() as session:
        session.add(Chat(id=NEW, title="New group"))
        await session.flush()
        session.add_all(
            [
                Membership(chat_id=NEW, user_id=1, opted_in=False),
                PointEvent(chat_id=NEW, user_id=1, delta=15, reason="test", ref_id="a"),
                ContentUsage(chat_id=NEW, content_key="sample"),
            ]
        )
    await runtime.migrations.migrate(-1, NEW)
    async with sessions() as session:
        assert not (await session.get(Membership, (NEW, 1))).opted_in
        assert (await session.scalars(select(Challenge))).one().status == "cancelled"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 15
    assert not runtime.pending.contains(NEW, 1)


@pytest.mark.parametrize("reverse", [False, True])
async def test_service_updates_migrate_chat(group_app, sessions, reverse):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await feed(
        Update.model_validate(
            {
                "update_id": 50,
                "message": {
                    "message_id": 100,
                    "date": int(utc_now().timestamp()),
                    "chat": {
                        "id": NEW if reverse else -1,
                        "type": "supergroup" if reverse else "group",
                    },
                    "migrate_from_chat_id" if reverse else "migrate_to_chat_id": -1
                    if reverse
                    else NEW,
                },
            }
        )
    )
    assert runtime.migrations.resolve(-1) == NEW


async def test_sender_handles_telegram_migration_and_retries_new_destination(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    original = transport.make_request
    destinations = []

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, SendMessage):
            destinations.append(method.chat_id)
            if method.chat_id == -1:
                raise TelegramMigrateToChat(
                    method=method, message="migrated", migrate_to_chat_id=NEW
                )
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        sent = await runtime.sender.send(-1, lambda: runtime.daily.bot.send_message(-1, "test"))
    assert sent is not None and destinations == [-1, NEW]
    async with sessions() as session:
        assert not (await session.get(Chat, -1)).is_active


async def test_slow_bulk_batch_cannot_delay_game_deadline(sessions):
    now = utc_now()
    async with sessions.begin() as session:
        from bot.db.models import User

        session.add_all(
            [
                Chat(id=-1, title="Test", bot_is_admin=True, next_daily_at=now),
                User(id=1, first_name="Test"),
            ]
        )
        await session.flush()
        session.add(GameSession(chat_id=-1, game="quiz", started_by=1, phase_deadline_at=now))
    started, release = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        started.set()
        await release.wait()
        return True

    deadline = AsyncMock(return_value=True)
    scheduler = Scheduler(sessions, hooks={"daily": slow, "game": deadline})
    bulk = asyncio.create_task(scheduler.tick(now))
    try:
        await asyncio.wait_for(started.wait(), 2)
        assert (await asyncio.wait_for(scheduler.deadline_tick(now), 2))["game"] == 1
        assert not bulk.done()
        deadline.assert_awaited_once()
    finally:
        release.set()
        await bulk


async def test_global_send_pause_cannot_delay_expiry_state(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await seed(runtime, sessions)
    async with sessions() as session:
        challenge = (await session.scalars(select(Challenge))).one()
    runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
    counts = await asyncio.wait_for(runtime.scheduler.deadline_tick(challenge.deadline_at), 2)
    assert counts["expire"] == 1
    async with sessions() as session:
        assert (await session.get(Challenge, challenge.id)).status == "missed"
    assert runtime.effects.tasks  # queued notification is independent of the committed deadline


@pytest.mark.parametrize("command", ["/sozlamalar", "/vazifa"])
@pytest.mark.parametrize("own_chat", [True, False])
async def test_anonymous_admin_only_trusted_for_own_chat(group_app, command, own_chat):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    update = command_update(command, user_id=108)
    message = update.message.model_copy(
        update={
            "from_user": tg_user(108, True),
            "sender_chat": update.message.chat.model_copy(update={"id": -1 if own_chat else -55}),
        }
    )
    await feed(update.model_copy(update={"message": message}))
    assert (transport.methods[-1].text == texts.ADMINS_ONLY) is not own_chat
    if own_chat and command == "/sozlamalar":
        assert transport.methods[-1].text == texts.SETTINGS_TITLE


async def test_join_member_check_failure_has_accurate_message(group_app):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, GetChatMember):
            raise RuntimeError("offline")
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        await feed(command_update("/qoshilish"))
    assert transport.methods[-1].text == texts.MEMBER_CHECK_FAILED


@pytest.mark.parametrize("kind", ["daily", "challenge", "weekly"])
async def test_failed_scheduled_hook_backs_off_ten_minutes_and_logs(sessions, caplog, kind):
    now = utc_now()
    async with sessions.begin() as session:
        session.add(Chat(id=-1, title="Test", bot_is_admin=True, **{f"next_{kind}_at": now}))
    scheduler = Scheduler(sessions, hooks={kind: AsyncMock(return_value=False)})
    assert (await scheduler.tick(now))[kind] == 1
    async with sessions() as session:
        assert getattr(await session.get(Chat, -1), f"next_{kind}_at") == now + timedelta(
            minutes=10
        )
    assert "backing off" in caplog.text
    assert (await scheduler.tick(now + timedelta(seconds=30)))[kind] == 0


async def test_anonymous_admin_can_answer_setting_prompt(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await feed(callback("sp:daily_time"))
    update = command_update("22:15", 101, 108)
    reply = update.message.model_copy(
        update={
            "from_user": tg_user(108, True),
            "sender_chat": update.message.chat,
            "reply_to_message": update.message.model_copy(update={"message_id": 100}),
            "entities": [],
        }
    )
    await feed(update.model_copy(update={"message": reply}))
    async with sessions() as session:
        assert (await session.get(Chat, -1)).daily_time.strftime("%H:%M") == "22:15"
    assert not runtime.setting_prompts.pending
