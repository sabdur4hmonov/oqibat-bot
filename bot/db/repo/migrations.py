"""Atomic Telegram chat-ID migration; aliases retain the inactive source row."""

from contextlib import AsyncExitStack
from copy import deepcopy

from sqlalchemy import and_, select, update
from sqlalchemy.orm import aliased

from bot.db.models import (
    Achievement,
    Challenge,
    Chat,
    ContentUsage,
    GameSession,
    Membership,
    PointEvent,
    ScheduledPost,
)
from bot.utils.time import utc_now

CHILDREN = (
    Membership,
    PointEvent,
    Challenge,
    ContentUsage,
    ScheduledPost,
    GameSession,
    Achievement,
)


class MigrationConflict(ValueError):
    """Conflicting ledger copies must be reviewed rather than silently changing points."""


async def merge_collisions(session, old_id: int, new_id: int) -> None:
    for model, keys in (
        (Membership, ("user_id",)),
        (Achievement, ("user_id", "key")),
        (ContentUsage, ("content_key",)),
        (ScheduledPost, ("kind", "local_date")),
    ):
        target = aliased(model)
        rows = (
            await session.execute(
                select(model, target)
                .join(target, and_(*[getattr(model, key) == getattr(target, key) for key in keys]))
                .where(model.chat_id == old_id, target.chat_id == new_id)
            )
        ).all()
        for source, destination in rows:
            if model is Membership:
                destination.opted_in = source.opted_in and destination.opted_in
                destination.is_active = source.is_active and destination.is_active
                destination.consecutive_misses = max(
                    source.consecutive_misses, destination.consecutive_misses
                )
                for field in ("last_seen_at", "last_picked_at", "opted_in_at"):
                    values = [
                        value
                        for value in (getattr(source, field), getattr(destination, field))
                        if value
                    ]
                    setattr(destination, field, max(values) if values else None)
                if not destination.opted_in:
                    destination.opted_in_at = None
            elif model is Achievement:
                destination.unlocked_at = min(source.unlocked_at, destination.unlocked_at)
                for field in ("claimed_at", "announced_at"):
                    values = [
                        value
                        for value in (getattr(source, field), getattr(destination, field))
                        if value
                    ]
                    setattr(destination, field, min(values) if values else None)
            elif model is ContentUsage:
                destination.used_at = max(source.used_at, destination.used_at)
            else:
                rank = {"failed": 0, "reserved": 1, "skipped": 2, "sent": 3}
                if rank.get(source.status, 0) > rank.get(destination.status, 0):
                    for field in (
                        "status",
                        "message_id",
                        "origin_chat_id",
                        "posted_at",
                        "claimed_at",
                        "sent_at",
                        "content_key",
                    ):
                        setattr(destination, field, getattr(source, field))
            await session.delete(source)
    target_event = aliased(PointEvent)
    duplicates = (
        await session.execute(
            select(PointEvent, target_event)
            .join(
                target_event,
                (PointEvent.user_id == target_event.user_id)
                & (PointEvent.reason == target_event.reason)
                & (PointEvent.ref_id == target_event.ref_id),
            )
            .where(
                PointEvent.chat_id == old_id,
                target_event.chat_id == new_id,
                PointEvent.ref_id.is_not(None),
            )
        )
    ).all()
    for source, destination in duplicates:
        if source.delta != destination.delta:
            raise MigrationConflict("Conflicting point-event references during chat migration")
        await session.delete(source)
    for model, statuses in ((Challenge, ["pending"]), (GameSession, ["lobby", "running"])):
        query = select(model).where(model.chat_id.in_([old_id, new_id]), model.status.in_(statuses))
        if model is GameSession:
            query = query.where(GameSession.game.not_in(["duel", "secret"]))
        active = (await session.scalars(query.order_by(model.created_at, model.id))).all()
        for duplicate in active[1:]:
            duplicate.status = "cancelled"
            if model is Challenge:
                duplicate.resolved_at = utc_now()
            else:
                duplicate.phase_deadline_at = None
    await session.flush()

    background = (
        await session.scalars(
            select(GameSession)
            .where(
                GameSession.chat_id.in_([old_id, new_id]),
                GameSession.game == "secret",
                GameSession.status.in_(["lobby", "running"]),
            )
            .order_by(GameSession.created_at, GameSession.id)
        )
    ).all()
    for duplicate in background[1:]:
        duplicate.status, duplicate.phase_deadline_at = "cancelled", None
    await session.flush()


async def snapshot(session, destination, migrated_at):
    new_id = destination.id
    participants = (
        await session.scalars(
            select(Membership.user_id).where(
                Membership.chat_id == new_id,
                Membership.opted_in.is_(True),
                Membership.is_active.is_(True),
            )
        )
    ).all()
    pending = (
        await session.scalars(
            select(Challenge)
            .where(Challenge.chat_id == new_id, Challenge.status == "pending")
            .execution_options(populate_existing=True)
        )
    ).all()
    games = (
        await session.scalars(
            select(GameSession)
            .where(GameSession.chat_id == new_id, GameSession.status.in_(["lobby", "running"]))
            .execution_options(populate_existing=True)
        )
    ).all()
    post = await session.scalar(
        select(ScheduledPost)
        .where(
            ScheduledPost.chat_id == new_id,
            ScheduledPost.kind == "daily",
            ScheduledPost.status == "sent",
        )
        .order_by(ScheduledPost.posted_at.desc())
        .limit(1)
    )
    return {
        "chat": destination,
        "participants": participants,
        "pending": pending,
        "games": games,
        "post": post,
        "migrated_at": migrated_at,
    }


class ChatMigrationRepository:
    def __init__(self, sessions, locks) -> None:
        self.sessions, self.locks = sessions, locks

    async def migrate(self, old_id: int, new_id: int):
        async with AsyncExitStack() as stack:
            for chat_id in sorted({old_id, new_id}):
                await stack.enter_async_context(self.locks.for_chat(chat_id))
            async with self.sessions.begin() as session:
                old = await session.get(Chat, old_id)
                if old is None:
                    old = Chat(id=old_id, title="", is_active=True, bot_is_admin=False)
                    session.add(old)
                    await session.flush()
                destination = await session.get(Chat, new_id)
                if old.migrated_to_chat_id == new_id:
                    if destination is None:
                        raise MigrationConflict("Migration target row is missing")
                    return await snapshot(session, destination, old.updated_at)
                for model in (Challenge, ScheduledPost):
                    await session.execute(
                        update(model)
                        .where(model.chat_id == old_id, model.origin_chat_id.is_(None))
                        .values(origin_chat_id=old_id)
                    )
                data = {
                    column.name: getattr(old, column.name)
                    for column in Chat.__table__.columns
                    if column.name not in {"id", "migrated_to_chat_id"}
                }
                if destination is None:
                    destination = Chat(id=new_id, **data)
                    session.add(destination)
                else:
                    await merge_collisions(session, old_id, new_id)
                    title = destination.title or data["title"]
                    for key, value in data.items():
                        setattr(destination, key, value)
                    destination.title = title
                destination.migrated_to_chat_id = None
                old.is_active, old.bot_is_admin = False, False
                old.next_daily_at = old.next_challenge_at = old.next_weekly_at = None
                old.next_season_at = None
                old.migrated_to_chat_id = new_id
                old.updated_at = utc_now()
                await session.flush()
                source_games = (
                    await session.scalars(
                        select(GameSession.id).where(GameSession.chat_id == old_id)
                    )
                ).all()
                # Telegram message IDs change scope at migration. Preserve the
                # content's origin even for finished/private-game history, so an
                # old hide button cannot delete a different supergroup message.
                content_games = await session.stream_scalars(
                    select(GameSession)
                    .where(
                        GameSession.chat_id == old_id,
                        GameSession.game.in_(["kim", "telephone", "memory"]),
                    )
                    .execution_options(yield_per=100)
                )
                async for game in content_games:
                    state = deepcopy(game.state)
                    for item in state.get("items", {}).values():
                        if item.get("message_id") is not None:
                            item.setdefault("origin_chat_id", old_id)
                    game.state = state
                await session.flush()
                for model in CHILDREN:
                    await session.execute(
                        update(model).where(model.chat_id == old_id).values(chat_id=new_id)
                    )
                pending_now = (
                    await session.scalars(
                        select(Challenge)
                        .where(Challenge.chat_id == new_id, Challenge.status == "pending")
                        .execution_options(populate_existing=True)
                    )
                ).all()
                for challenge in pending_now:
                    member = await session.get(Membership, (new_id, challenge.user_id))
                    if member is None or not member.opted_in or not member.is_active:
                        challenge.status, challenge.resolved_at = "cancelled", utc_now()
                # Keep original message IDs for audit; their origin marks changed ordering scope.
                games = (
                    await session.scalars(
                        select(GameSession)
                        .where(
                            GameSession.chat_id == new_id,
                            GameSession.status.in_(["lobby", "running"]),
                        )
                        .execution_options(populate_existing=True)
                    )
                ).all()
                for game in games:
                    if game.id in source_games:
                        state = dict(game.state)
                        state.pop("seen", None)
                        if "answer_after_id" in state:
                            state["answer_after_id"] = 0
                        for field in ("board_id", "poll_message_id"):
                            if state.get(field):
                                state[f"migrated_{field}"] = state[field]
                                state[field] = None
                        game.state = state
                await session.flush()
                result = await snapshot(session, destination, old.updated_at)
            return result
