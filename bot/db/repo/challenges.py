"""Persistence hooks keep pending membership synchronized only after successful commits."""

from bot.db.models import Challenge
from bot.utils.time import utc_now


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
                self.pending.add(challenge_id, challenge.chat_id, challenge.user_id)
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
