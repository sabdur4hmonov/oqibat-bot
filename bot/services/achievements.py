"""Ledger-derived streaks and idempotent per-chat milestones; no mutable balance."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot import texts
from bot.db.models import Achievement, Challenge, Chat, PointEvent, User
from bot.services.sender import Priority
from bot.utils.time import is_quiet, utc_now

KEYS = ("first_task", "first_video", "ten_krok", "first_mafia_win", "streak7", "streak30")


def streak_length(days, end):
    days, result = set(days), 0
    while end in days:
        result += 1
        end -= timedelta(days=1)
    return result


def longest_streak(days):
    best = count = 0
    last = None
    for day in sorted(set(days)):
        count = count + 1 if last is not None and day == last + timedelta(days=1) else 1
        best, last = max(best, count), day
    return best


async def unlock(session, chat, user, key):
    insert = pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(Achievement)
        .values(chat_id=chat, user_id=user, key=key, unlocked_at=utc_now())
        .on_conflict_do_nothing(
            index_elements=[Achievement.chat_id, Achievement.user_id, Achievement.key]
        )
    )


async def checkin_milestones(session, chat, user, ref):
    from bot.services.points import record_event

    end = date.fromisoformat(ref.removeprefix("daily:"))
    refs = (
        await session.scalars(
            select(PointEvent.ref_id).where(
                PointEvent.chat_id == chat,
                PointEvent.user_id == user,
                PointEvent.reason == "daily_checkin",
                PointEvent.ref_id >= f"daily:{end - timedelta(days=31)}",
                PointEvent.ref_id <= ref,
            )
        )
    ).all()
    count = streak_length([date.fromisoformat(value[6:]) for value in refs], end)
    if count in (7, 30):
        await record_event(session, chat, user, 3 if count == 7 else 10, "streak_bonus", ref)
    if count >= 7:
        await unlock(session, chat, user, "streak7")
    if count >= 30:
        await unlock(session, chat, user, "streak30")


async def on_event(session, chat, user, delta, reason, ref):
    if reason == "challenge_done" and delta > 0:
        await unlock(session, chat, user, "first_task")
        if ref and ref.startswith("challenge:") and ref[10:].isdigit():
            task = await session.get(Challenge, int(ref[10:]))
            if task and task.kind == "video_note":
                await unlock(session, chat, user, "first_video")
    elif reason == "krokodil" and delta == 5:
        count = await session.scalar(
            select(func.count())
            .select_from(PointEvent)
            .where(
                PointEvent.chat_id == chat,
                PointEvent.user_id == user,
                PointEvent.reason == reason,
                PointEvent.delta == 5,
            )
        )
        if count >= 10:
            await unlock(session, chat, user, "ten_krok")
    elif reason == "mafia_win" and delta > 0:
        await unlock(session, chat, user, "first_mafia_win")
    elif reason == "daily_checkin":
        await checkin_milestones(session, chat, user, ref)


class Achievements:
    def __init__(self, runtime):
        self.runtime = runtime

    async def list(self, chat, user, *, reconcile=False):
        async with self.runtime.locks.hold(chat) as chat:
            async with self.runtime.sessions.begin() as session:
                if reconcile:
                    events = (
                        await session.execute(
                            select(PointEvent.reason, PointEvent.delta, PointEvent.ref_id).where(
                                PointEvent.chat_id == chat, PointEvent.user_id == user
                            )
                        )
                    ).all()
                    done = {row.reason for row in events if row.delta > 0}
                    keys = []
                    if "challenge_done" in done:
                        keys.append("first_task")
                    if "mafia_win" in done:
                        keys.append("first_mafia_win")
                    if sum(row.reason == "krokodil" and row.delta == 5 for row in events) >= 10:
                        keys.append("ten_krok")
                    if await session.scalar(
                        select(Challenge.id)
                        .where(
                            Challenge.chat_id == chat,
                            Challenge.user_id == user,
                            Challenge.status == "done",
                            Challenge.kind == "video_note",
                        )
                        .limit(1)
                    ):
                        keys.append("first_video")
                    best = longest_streak(
                        date.fromisoformat(row.ref_id[6:])
                        for row in events
                        if row.reason == "daily_checkin"
                        and row.ref_id
                        and row.ref_id.startswith("daily:")
                    )
                    if best >= 7:
                        keys.append("streak7")
                    if best >= 30:
                        keys.append("streak30")
                    for key in keys:
                        await unlock(session, chat, user, key)
                return (
                    await session.scalars(
                        select(Achievement)
                        .where(Achievement.chat_id == chat, Achievement.user_id == user)
                        .order_by(Achievement.key)
                    )
                ).all()

    async def announce(self, now):
        async with self.runtime.sessions() as session:
            rows = (
                await session.scalars(
                    select(Achievement)
                    .where(Achievement.claimed_at.is_(None))
                    .order_by(Achievement.unlocked_at)
                    .limit(500)
                )
            ).all()
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.chat_id].append(row)
        for chat_id, batch in grouped.items():
            generation = self.runtime.sender.generations.get(chat_id, 0)
            async with self.runtime.locks.hold(chat_id) as chat_id:
                async with self.runtime.sessions.begin() as session:
                    chat = await session.get(Chat, chat_id)
                    if (
                        not chat
                        or not chat.is_active
                        or not chat.bot_is_admin
                        or is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end)
                    ):
                        continue
                    items = []
                    for row in batch[:10]:
                        current = await session.get(Achievement, (chat_id, row.user_id, row.key))
                        if current is None or current.claimed_at:
                            continue
                        current.claimed_at = now  # Accepted loss for low-priority announcements.
                        user = await session.get(User, row.user_id)
                        if user and row.unlocked_at >= now - timedelta(hours=6):
                            items.append((row.user_id, user.first_name, row.key))
            if not items or generation != self.runtime.sender.generations.get(chat_id, 0):
                continue
            sent = await self.runtime.sender.send(
                chat_id,
                lambda chat_id=chat_id, items=items: self.runtime.game_hub.bot.send_message(
                    chat_id, texts.achievement_batch(items)
                ),
                priority=Priority.BULK,
            )
            if sent is not None:
                async with self.runtime.sessions.begin() as session:
                    for user, _, key in items:
                        row = await session.get(Achievement, (chat_id, user, key))
                        if row:
                            row.announced_at = now
