"""All game state writes share a chat lock; never send Telegram messages under it."""

from copy import deepcopy
from dataclasses import dataclass

from sqlalchemy import select

from bot.db.models import Challenge, Chat, GameSession, Membership
from bot.services.game_cache import view
from bot.services.points import record_event
from bot.utils.time import utc_now


@dataclass(frozen=True)
class Award:
    user_id: int
    delta: int
    reason: str
    ref_id: str


class GameBusy(ValueError):
    pass


class GameSessionRepository:
    def __init__(self, sessions, locks, cache=None, pending=None) -> None:
        self.sessions, self.locks = sessions, locks
        self.cache = cache
        self.pending = pending

    async def create(self, chat_id: int, **values) -> int:
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                game = GameSession(chat_id=chat_id, **values)
                session.add(game)
                await session.flush()
                game_id = game.id
            if self.cache:
                self.cache.sync(game)
            return game_id

    async def start(
        self, chat_id: int, user_id: int, game: str, state: dict, deadline, status="running"
    ):
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                chat = await session.get(Chat, chat_id)
                member = await session.get(Membership, (chat_id, user_id))
                if (
                    chat is None
                    or not chat.is_active
                    or not chat.bot_is_admin
                    or member is None
                    or not member.opted_in
                    or not member.is_active
                ):
                    return None
                if game == "hyj" or (game == "rps" and state.get("target") is not None):
                    target = await session.get(Membership, (chat_id, state.get("target")))
                    if target is None or not target.opted_in or not target.is_active:
                        return None
                query = select(GameSession.id).where(
                    GameSession.chat_id == chat_id, GameSession.status.in_(["lobby", "running"])
                )
                if game == "duel":
                    query = query.where(
                        GameSession.game == "duel", GameSession.started_by == user_id
                    )
                elif game == "secret":
                    query = query.where(GameSession.game == "secret")
                else:
                    query = query.where(GameSession.game.not_in(["duel", "secret"]))
                if await session.scalar(query.limit(1)) is not None:
                    raise GameBusy()
                row = GameSession(
                    chat_id=chat_id,
                    game=game,
                    status=status,
                    started_by=user_id,
                    state={"display_tz": chat.tz, **state, "rev": 0},
                    phase_deadline_at=deadline,
                )
                session.add(row)
                await session.flush()
            if self.cache:
                self.cache.sync(row)
            return view(row)

    async def transition(self, chat_id: int, game_id: int, transform, *, expected_rev=None):
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                row = await session.get(GameSession, game_id)
                if row is None or row.chat_id != chat_id or row.status not in {"lobby", "running"}:
                    return None
                if expected_rev is not None and row.state.get("rev", 0) != expected_rev:
                    return None
                row.state = deepcopy(row.state)
                chat = await session.get(Chat, chat_id)
                allowed = chat is not None and chat.is_active and chat.bot_is_admin
                if allowed:
                    awards = transform(row)
                    if awards is False:
                        return None
                else:
                    row.status, row.phase_deadline_at = "cancelled", None
                    row.state["phase"] = "done"
                    awards = []
                row.state = {**row.state, "rev": row.state.get("rev", 0) + 1}
                for award in awards or []:
                    await record_event(
                        session, chat_id, award.user_id, award.delta, award.reason, award.ref_id
                    )
            if self.cache:
                self.cache.sync(row)
            return view(row) if allowed else None

    async def refuse_hyj(self, chat_id, game_id, user_id):
        """Cancel a linked pending dare and record only refusal, in one transaction."""
        challenge_id = None
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                game = await session.get(GameSession, game_id)
                member = await session.get(Membership, (chat_id, user_id))
                chat = await session.get(Chat, chat_id)
                if (
                    game is None
                    or game.chat_id != chat_id
                    or game.game != "hyj"
                    or game.status not in {"lobby", "running"}
                    or game.state.get("target") != user_id
                    or member is None
                    or not member.opted_in
                    or not member.is_active
                    or chat is None
                    or not chat.is_active
                    or not chat.bot_is_admin
                    or game.phase_deadline_at is None
                    or game.phase_deadline_at <= utc_now()
                ):
                    return None
                challenge = await session.scalar(
                    select(Challenge).where(Challenge.game_session_id == game_id).limit(1)
                )
                if challenge:
                    if challenge.status != "pending" or challenge.deadline_at <= utc_now():
                        return None
                    challenge.status, challenge.resolved_at = "cancelled", utc_now()
                    challenge_id = challenge.id
                game.status, game.phase_deadline_at = "finished", None
                game.state = {
                    **game.state,
                    "phase": "done",
                    "result": "refused",
                    "rev": game.state.get("rev", 0) + 1,
                }
                await record_event(session, chat_id, user_id, -2, "hyj_refuse", f"game:{game_id}")
            if challenge_id is not None and self.pending:
                self.pending.remove(challenge_id)
            if self.cache:
                self.cache.sync(game)
            return view(game)

    async def claim_result_card(self, chat_id, game_id):
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                row = await session.get(GameSession, game_id)
                chat = await session.get(Chat, chat_id)
                if (
                    row is None
                    or row.chat_id != chat_id
                    or row.status != "finished"
                    or row.state.get("result_card_claimed")
                    or chat is None
                    or not chat.is_active
                    or not chat.bot_is_admin
                ):
                    return False
                row.state = {
                    **row.state,
                    "result_card_claimed": True,
                    "result_card_status": "reserved",
                }
            return True

    async def record_result_card(self, chat_id, game_id, sent):
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                row = await session.get(GameSession, game_id)
                if (
                    row
                    and row.chat_id == chat_id
                    and row.state.get("result_card_status") == "reserved"
                ):
                    row.state = {
                        **row.state,
                        "result_card_status": "sent" if sent is not None else "failed",
                        "result_card_message_id": getattr(sent, "message_id", None),
                        "result_card_origin_chat_id": getattr(
                            getattr(sent, "chat", None), "id", None
                        ),
                    }

    async def change(self, chat_id: int, game_id: int, transform) -> bool:
        """transform is synchronous and changes only this locked ORM game object."""
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                game = await session.get(GameSession, game_id)
                if game is None or game.chat_id != chat_id:
                    return False
                game.state = deepcopy(game.state)
                transform(game)
                # Assign a fresh object so SQLAlchemy detects in-place JSON changes.
                game.state = deepcopy(game.state)
            if self.cache:
                self.cache.sync(game)
            return True
