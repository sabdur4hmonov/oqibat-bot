"""Role distribution is pure; names are internal identifiers, not bot text."""

import random

MAFIA, DOCTOR, COMMISSIONER, TOWN = "mafia", "doctor", "commissioner", "town"
DON, MISTRESS, SERIAL = "don", "mistress", "manyak"


def is_mafia(role):
    return role in {MAFIA, DON}


def side(role):
    return "mafia" if is_mafia(role) else "manyak" if role == SERIAL else "town"


def distribution(count: int, extended=False) -> list[str]:
    if not 5 <= count <= 15:
        raise ValueError("Mafia needs 5-15 players")
    mafia = 1 if count <= 6 else 2 if count <= 9 else 3
    result = [MAFIA] * mafia + [DOCTOR, COMMISSIONER] + [TOWN] * (count - mafia - 2)
    if extended:
        if count >= 8:
            result[0] = DON
        if count >= 9:
            result[result.index(TOWN)] = MISTRESS
        if count >= 11:
            result[result.index(TOWN)] = SERIAL
    return result


def assign(players, rng=None, *, extended=False) -> dict[str, str]:
    players = [str(player) for player in players]
    if len(set(players)) != len(players):
        raise ValueError("Duplicate Mafia player")
    roles = distribution(len(players), extended)
    (rng or random).shuffle(roles)
    return dict(zip(players, roles, strict=True))
