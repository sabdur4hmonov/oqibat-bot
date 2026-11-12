"""Pure bounded higher/lower game; caller supplies the secret and UTC clock."""

from copy import deepcopy

MAX_GUESSES = 15
COOLDOWN = 3


def parse_guess(text):
    if not isinstance(text, str):
        return None
    value = text.strip()
    if not 1 <= len(value) <= 3 or not value.isascii() or not value.isdecimal():
        return None
    value = int(value)
    return value if 1 <= value <= 100 else None


def initial(secret):
    if type(secret) is not int or not 1 <= secret <= 100:
        raise ValueError("Invalid secret")
    return {
        "phase": "preparing",
        "round": 1,
        "secret": secret,
        "low": 1,
        "high": 100,
        "attempts": 0,
        "last_message_id": 0,
        "cooldowns": {},
        "names": {},
        "scores": {},
    }


def guess(state, user, name, value, message_id, now):
    key = str(user)
    if (
        state.get("phase") != "playing"
        or type(user) is not int
        or user <= 0
        or type(value) is not int
        or not state["low"] <= value <= state["high"]
        or type(message_id) is not int
        or message_id <= state["last_message_id"]
        or (key in state["cooldowns"] and now - state["cooldowns"][key] < COOLDOWN)
    ):
        return None
    result = deepcopy(state)
    result["last_message_id"] = message_id
    result["cooldowns"][key] = now
    result["names"][key] = name
    result["attempts"] += 1
    if value == state["secret"]:
        result.update(phase="done", result="found", winner=user, scores={key: 3})
    else:
        result["hint"] = "higher" if value < state["secret"] else "lower"
        result["last_guess"] = value
        result["low" if value < state["secret"] else "high"] = value + (
            1 if value < state["secret"] else -1
        )
        if result["attempts"] >= MAX_GUESSES:
            result.update(phase="done", result="limit")
    return result


def expire(state):
    result = deepcopy(state)
    result.update(phase="done", result="timeout")
    return result
