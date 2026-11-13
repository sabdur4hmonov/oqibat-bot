import asyncio
from datetime import time, timedelta

import pytest
from aiogram.types import Update
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_group_flows import bot_update, tg_user
from test_group_flows import group_app as group_app

from bot import texts
from bot.db.models import Challenge, Membership, PointEvent
from bot.utils.time import utc_now


@pytest.fixture
async def challenge_app(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await runtime.groups.change_setting(-1, "quiet_start", time())
    await runtime.groups.change_setting(-1, "quiet_end", time())
    await runtime.groups.membership(-1, tg_user(1), opted_in=True)
    async with sessions.begin() as session:
        (await session.get(Membership, (-1, 1))).consecutive_misses = 2
    return feed, transport, runtime


def video_update(message_id=101, user=1, kind="video_note"):
    media = {"file_id": "test", "file_unique_id": "unique", "duration": 1}
    if kind == "video_note":
        media["length"] = 100
    return Update.model_validate(
        {
            "update_id": message_id,
            "message": {
                "message_id": message_id,
                "date": int(utc_now().timestamp()),
                "chat": {"id": -1, "type": "group"},
                "from": tg_user(user).model_dump(),
                kind: media,
            },
        }
    )


async def test_round_video_completion_awards_15_once_and_resets_streak(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    assert await runtime.challenge_service.assign(-1, "video_note", force=True) is None
    assert "&lt;Sinov&gt;" in transport.methods[-1].text
    await feed(video_update(user=2))
    await feed(video_update(kind="voice"))
    assert runtime.pending.for_chat(-1)
    await asyncio.gather(feed(video_update(102)), feed(video_update(103)))
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 15
        assert (await session.scalars(select(Challenge))).one().status == "done"
        assert (await session.get(Membership, (-1, 1))).consecutive_misses == 0
    assert not runtime.pending.for_chat(-1)


@pytest.mark.parametrize("mode,expected", [("points", -5), ("off", 0)])
async def test_expiry_penalty_and_daily_debtor_announcement(
    challenge_app, sessions, mode, expected
):
    feed, transport, runtime = challenge_app
    await runtime.groups.change_setting(-1, "penalty_mode", mode)
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    async with sessions() as session:
        challenge = (await session.scalars(select(Challenge))).one()
    assert await runtime.challenge_service.expire(
        challenge, challenge.deadline_at + timedelta(seconds=1)
    )
    assert not await runtime.challenge_service.expire(
        challenge, challenge.deadline_at + timedelta(seconds=2)
    )
    await runtime.effects.drain()
    assert (await runtime.points.stats(-1, 1))[0] == expected
    chat = await runtime.groups.get(-1)
    await runtime.daily.post(chat, utc_now())
    assert ("Vazifasi qolgan" in transport.methods[-1].text) == (mode == "points")


async def test_one_pending_per_chat_and_database_constraint(challenge_app):
    feed, transport, runtime = challenge_app
    assert await runtime.challenge_service.assign(-1, "video_note", force=True) is None
    assert (
        await runtime.challenge_service.assign(-1, "voice", force=True) == texts.PENDING_CHALLENGE
    )
    with pytest.raises(IntegrityError):
        await runtime.challenges.create(
            chat_id=-1,
            user_id=1,
            kind="voice",
            prompt_key="test",
            deadline_at=utc_now() + timedelta(hours=1),
        )
    assert len(runtime.pending.for_chat(-1)) == 1


def command_update(text, message_id=110, user_id=1):
    command = text.split()[0]
    return Update.model_validate(
        {
            "update_id": message_id,
            "message": {
                "message_id": message_id,
                "date": int(utc_now().timestamp()),
                "chat": {"id": -1, "type": "group"},
                "from": tg_user(user_id).model_dump(),
                "text": text,
                "entities": [{"type": "bot_command", "offset": 0, "length": len(command)}],
            },
        }
    )


async def test_men_and_top_show_ledger_totals_with_escaped_names(challenge_app):
    feed, transport, runtime = challenge_app
    await runtime.challenge_service.assign(-1, "video_note", force=True)
    await feed(video_update())
    await feed(command_update("/men"))
    assert "Jami: 15 ball" in transport.methods[-1].text
    assert "&lt;Sinov&gt;" in transport.methods[-1].text
    await feed(command_update("/top", 111))
    assert "Joriy mavsum" in transport.methods[-1].text and "15 ball" in transport.methods[-1].text


async def test_assignment_command_cannot_complete_its_own_text_task(challenge_app, sessions):
    feed, transport, runtime = challenge_app
    await runtime.groups.membership(-1, tg_user(1), opted_in=False)
    await runtime.groups.membership(-1, tg_user(42), opted_in=True)
    runtime.content.banks["challenges"] = [
        {"key": "test_text", "kind": "text", "text": "Yangi xabar yozing."}
    ]
    await feed(command_update("/vazifa matn", 1, 42))
    async with sessions() as session:
        assert (await session.scalars(select(Challenge))).one().status == "pending"
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
