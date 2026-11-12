"""Pure one-round rock-paper-scissors; choices stay private until both are locked."""

from copy import deepcopy

MOVES = ("r", "s", "p")
BEATS = {"r": "s", "s": "p", "p": "r"}


def winner(first: str, second: str) -> int | None:
    """Return winning player index, or None for a draw."""
    if first not in MOVES or second not in MOVES:
        raise ValueError("Invalid move")
    if first == second:
        return None
    return 0 if BEATS[first] == second else 1


def accept(state: dict, user: int, name: str) -> dict:
    if (
        state.get("phase") != "lobby"
        or type(user) is not int
        or user <= 0
        or user in state["players"]
        or state.get("target") not in {None, user}
    ):
        raise ValueError("Not an eligible opponent")
    result = deepcopy(state)
    result["players"].append(user)
    result["names"][str(user)] = name
    result.update(phase="choosing", choices={})
    return result


def choose(state: dict, user: int, move: str) -> dict:
    if (
        state.get("phase") != "choosing"
        or len(state.get("players", [])) != 2
        or type(user) is not int
        or user not in state["players"]
        or str(user) in state["choices"]
        or move not in MOVES
    ):
        raise ValueError("Invalid or repeated choice")
    result = deepcopy(state)
    result["choices"][str(user)] = move
    if len(result["choices"]) == 2:
        players = result["players"]
        outcome = winner(*(result["choices"][str(player)] for player in players))
        result.update(phase="done", winner=players[outcome] if outcome is not None else None)
    return result
