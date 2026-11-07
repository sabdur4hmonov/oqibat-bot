"""All game state writes share a chat lock; never send Telegram messages under it."""

from copy import deepcopy

from bot.db.models import GameSession


class GameSessionRepository:
    def __init__(self, sessions, locks) -> None:
        self.sessions, self.locks = sessions, locks

    async def create(self, chat_id: int, **values) -> int:
        async with self.locks.hold(chat_id) as chat_id:
            async with self.sessions.begin() as session:
                game = GameSession(chat_id=chat_id, **values)
                session.add(game)
                await session.flush()
                game_id = game.id
            return game_id

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
            return True
