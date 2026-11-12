"""Single-process admission shared by every private-input game, including Mafia."""

import asyncio

from bot.games.private_input import PRIVATE_GAMES


class PrivateContexts:
    def __init__(self, cache):
        self.cache = cache
        self.lock = asyncio.Lock()
        self.users = {}
        cache.listeners.append(self.sync)

    def sync(self, game, old=None):
        if game.game not in PRIVATE_GAMES:
            return
        previous = set((old or game).state.get("players", {}))
        current = (
            set(game.state.get("players", {})) if game.status in {"lobby", "running"} else set()
        )
        for user in previous - current:
            if self.users.get(int(user)) == game.id:
                self.users.pop(int(user), None)
        for user in current:
            self.users[int(user)] = game.id

    def get(self, user):
        game_id = self.users.get(user)
        return self.cache.get(game_id) if game_id else None
