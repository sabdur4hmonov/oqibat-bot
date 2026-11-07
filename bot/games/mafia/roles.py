"""Role distribution is pure; names are internal identifiers, not bot text."""

import random

MAFIA, DOCTOR, COMMISSIONER, TOWN = "mafia", "doctor", "commissioner", "town"


def distribution(count: int) -> list[str]:
    if not 5 <= count <= 15:
        raise ValueError("Mafia needs 5-15 players")
    mafia = 1 if count <= 6 else 2 if count <= 9 else 3
    return [MAFIA] * mafia + [DOCTOR, COMMISSIONER] + [TOWN] * (count - mafia - 2)


def assign(players, rng=None) -> dict[str, str]:
    players = [str(player) for player in players]
    if len(set(players)) != len(players):
        raise ValueError("Duplicate Mafia player")
    roles = distribution(len(players))
    (rng or random).shuffle(roles)
    return dict(zip(players, roles, strict=True))
