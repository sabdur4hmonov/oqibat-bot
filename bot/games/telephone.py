"""Pure voice-chain ordering, input limits and one-item-per-author rewards."""

import random


def player_order(players, rng=None):
    order = list(players)
    if not 4 <= len(order) <= 10 or len(set(order)) != len(order):
        raise ValueError("Telephone requires 4–10 unique players")
    (rng or random).shuffle(order)
    return order


def valid_voice(duration):
    return type(duration) is int and 0 <= duration <= 30


def rewards(items):
    return {str(item["user_id"]): 3 for item in items.values() if not item.get("hidden")}
