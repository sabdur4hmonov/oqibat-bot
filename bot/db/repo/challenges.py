"""Persistence hooks keep pending membership synchronized only after successful commits."""

from sqlalchemy import select, update

from bot.db.models import Challenge, Chat, ContentUsage, Membership, User
from bot.services.content import choose_content
from bot.services.penalties import challenge_deadline
from bot.services.picker import Candidate, pick_member
from bot.services.points import challenge_points, record_event
from bot.utils.time import is_quiet, utc_now


class ChallengeRepository:
    def __init__(self, sessions, pending, locks) -> None:
        self.sessions, self.pending, self.locks = sessions, pending, locks

    async def create(self, **values) -> int:
        async with self.locks.for_chat(values["chat_id"]):
            async with self.sessions.begin() as session:
                challenge = Challenge(**values)
                session.add(challenge)
                await session.flush()
                challenge_id = challenge.id
            if challenge.status == "pending":
                self.pending.add(
                    challenge_id,
                    challenge.chat_id,
                    challenge.user_id,
                    challenge.kind,
                    challenge.deadline_at,
                    challenge.created_at,
                )
            return challenge_id

    async def resolve(self, chat_id: int, challenge_id: int, status: str) -> bool:
        if status not in {"done", "missed", "cancelled"}:
            raise ValueError("Invalid challenge resolution")
        async with self.locks.for_chat(chat_id):
            async with self.sessions.begin() as session:
                challenge = await session.get(Challenge, challenge_id)
                if (
                    challenge is None
                    or challenge.chat_id != chat_id
                    or challenge.status != "pending"
                ):
                    return False
                challenge.status = status
                challenge.resolved_at = utc_now()
            self.pending.remove(challenge_id)
            return True

    async def assign(self, chat_id, now, items, kind=None, force=False):
        async with self.locks.for_chat(chat_id):
            if self.pending.for_chat(chat_id):
                return None
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                if chat is None or not chat.is_active or not chat.bot_is_admin:
                    return None
                if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end) or (
                    not force and chat.challenges_per_day == 0
                ):
                    return None
                members = (
                    await session.execute(
                        select(Membership, User)
                        .join(User)
                        .where(
                            Membership.chat_id == chat_id,
                            Membership.opted_in.is_(True),
                            Membership.is_active.is_(True),
                        )
                    )
                ).all()
                selected = pick_member(
                    [Candidate(member.user_id, member.last_picked_at) for member, _ in members], now
                )
                if selected is None:
                    return None
                member, user = next((m, u) for m, u in members if m.user_id == selected)
                used = dict(
                    (
                        await session.execute(
                            select(ContentUsage.content_key, ContentUsage.used_at).where(
                                ContentUsage.chat_id == chat_id
                            )
                        )
                    ).all()
                )
                item = choose_content(
                    [item for item in items if kind is None or item["kind"] == kind], used
                )
                if item is None:
                    return None
                challenge = Challenge(
                    chat_id=chat_id,
                    user_id=selected,
                    kind=item["kind"],
                    prompt_key=item["key"],
                    created_at=now,
                    deadline_at=challenge_deadline(
                        now, chat.challenge_hours, chat.tz, chat.quiet_start, chat.quiet_end
                    ),
                )
                session.add(challenge)
                member.last_picked_at = now
                await session.merge(
                    ContentUsage(chat_id=chat_id, content_key=item["key"], used_at=now)
                )
                await session.flush()
            self.pending.add(
                challenge.id,
                chat_id,
                selected,
                challenge.kind,
                challenge.deadline_at,
                challenge.created_at,
            )
            return challenge, user, chat, item

    async def set_message(self, chat_id: int, challenge_id: int, message_id: int) -> None:
        async with self.locks.for_chat(chat_id):
            async with self.sessions.begin() as session:
                await session.execute(
                    update(Challenge)
                    .where(Challenge.id == challenge_id, Challenge.status == "pending")
                    .values(message_id=message_id)
                )
            if challenge_id in self.pending.message_ids:
                self.pending.message_ids[challenge_id] = message_id

    async def complete(
        self, chat_id: int, challenge_id: int, user_id: int, kind: str, sent_at, message_id
    ):
        async with self.locks.for_chat(chat_id):
            async with self.sessions.begin() as session:
                challenge = await session.get(Challenge, challenge_id)
                member = await session.get(Membership, (chat_id, user_id))
                if (
                    challenge is None
                    or challenge.status != "pending"
                    or challenge.chat_id != chat_id
                    or challenge.user_id != user_id
                    or challenge.kind != kind
                    or challenge.message_id is None
                    or message_id <= challenge.message_id
                    or sent_at > challenge.deadline_at
                    or sent_at < challenge.created_at.replace(microsecond=0)
                    or member is None
                    or not member.opted_in
                    or not member.is_active
                ):
                    return None
                delta = challenge_points(kind, done=True)
                challenge.status, challenge.resolved_at = "done", utc_now()
                member.consecutive_misses = 0
                await record_event(
                    session, chat_id, user_id, delta, "challenge_done", f"challenge:{challenge_id}"
                )
            self.pending.remove(challenge_id)
            return delta

    async def expire(self, chat_id: int, challenge_id: int, now):
        outcome = None
        async with self.locks.for_chat(chat_id):
            async with self.sessions.begin() as session:
                challenge = await session.get(Challenge, challenge_id)
                if (
                    challenge is None
                    or challenge.chat_id != chat_id
                    or challenge.status != "pending"
                    or challenge.deadline_at > now
                ):
                    return None
                chat = await session.get(Chat, chat_id)
                member = await session.get(Membership, (chat_id, challenge.user_id))
                challenge.resolved_at = now
                if (
                    chat is None
                    or not chat.is_active
                    or not chat.bot_is_admin
                    or member is None
                    or not member.opted_in
                    or not member.is_active
                ):
                    challenge.status = "cancelled"
                else:
                    challenge.status = "missed"
                    challenge.miss_announced_at = None if chat.penalty_mode == "points" else now
                    member.consecutive_misses += 1
                    delta = challenge_points(
                        challenge.kind, done=False, penalty_mode=chat.penalty_mode
                    )
                    if delta:
                        await record_event(
                            session,
                            chat_id,
                            challenge.user_id,
                            delta,
                            "challenge_missed",
                            f"challenge:{challenge_id}",
                        )
                    outcome = (chat, challenge.user_id, member.consecutive_misses)
            self.pending.remove(challenge_id)
        return outcome
