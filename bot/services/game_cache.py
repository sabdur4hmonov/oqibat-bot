"""Active-game and poll lookup; ordinary messages never query inactive game state."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from bot.db.models import GameSession


@dataclass(frozen=True)
class GameView:
    id: int
    chat_id: int
    game: str
    status: str
    state: dict
    started_by: int
    phase_deadline_at: datetime | None


def view(game) -> GameView:
    return GameView(
        game.id,
        game.chat_id,
        game.game,
        game.status,
        deepcopy(game.state),
        game.started_by,
        game.phase_deadline_at,
    )


class GameCache:
    def __init__(self) -> None:
        self.records: dict[int, GameView] = {}
        self.by_chat: dict[int, set[int]] = {}
        self.by_poll: dict[str, int] = {}
        self.main_ids: dict[int, int] = {}
        self.listeners = []

    async def load(self, sessions) -> None:
        async with sessions() as session:
            rows = (
                await session.scalars(
                    select(GameSession).where(GameSession.status.in_(["lobby", "running"]))
                )
            ).all()
        self.records.clear()
        self.by_chat.clear()
        self.by_poll.clear()
        self.main_ids.clear()
        for game in rows:
            self.sync(game)

    def sync(self, game) -> None:
        old = self.records.pop(game.id, None)
        if old:
            self.by_chat[old.chat_id].discard(game.id)
            if not self.by_chat[old.chat_id]:
                del self.by_chat[old.chat_id]
            if old.state.get("poll_id"):
                self.by_poll.pop(old.state["poll_id"], None)
            if old.game != "duel":
                self.main_ids.pop(old.chat_id, None)
        if game.status not in {"lobby", "running"}:
            for listener in self.listeners:
                listener(game, old)
            return
        snapshot = view(game)
        self.records[game.id] = snapshot
        self.by_chat.setdefault(game.chat_id, set()).add(game.id)
        if game.game != "duel":
            self.main_ids[game.chat_id] = game.id
        if game.state.get("poll_id"):
            self.by_poll[game.state["poll_id"]] = game.id
        for listener in self.listeners:
            listener(game, old)

    def get(self, game_id: int) -> GameView | None:
        game = self.records.get(game_id)
        return deepcopy(game) if game else None

    def for_chat(self, chat_id: int) -> list[GameView]:
        return [self.get(game_id) for game_id in sorted(self.by_chat.get(chat_id, ()))]

    def main(self, chat_id: int) -> GameView | None:
        game_id = self.main_ids.get(chat_id)
        return self.get(game_id) if game_id is not None else None
