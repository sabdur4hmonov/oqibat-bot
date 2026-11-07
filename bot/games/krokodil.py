"""Pure Krokodil transitions and normalized word detection."""

from copy import deepcopy

from bot.utils.text_normalize import normalize_text


def matches(text: str, word: str) -> bool:
    expected = normalize_text(word)
    return bool(expected) and normalize_text(text) == expected


def reveals(text: str, word: str) -> bool:
    expected = normalize_text(word)
    return bool(expected) and f" {expected} " in f" {normalize_text(text)} "


def guess(state, user_id, text):
    if state.get("phase") != "playing" or not state.get("word"):
        return None
    host = state["host"]
    if not (reveals(text, state["word"]) if user_id == host else matches(text, state["word"])):
        return None
    result = deepcopy(state)
    result["last_result"] = {"word": state["word"], "host": host, "guesser": user_id}
    result.update(phase="preparing", word=None)
    if user_id == host:
        result["last_result"]["kind"] = "reveal"
        awards = [(host, -3)]
    else:
        result["last_result"]["kind"] = "guess"
        awards = [(user_id, 5), (host, 3)]
        result.update(host=user_id, round=state["round"] + 1, skips=0, end_at=None)
        if state["round"] == 10:
            result["phase"] = "done"
    for user, delta in awards:
        key = str(user)
        result.setdefault("scores", {})[key] = result.get("scores", {}).get(key, 0) + delta
    return result, awards


def skip(state, user_id):
    if state.get("phase") != "playing" or user_id != state["host"] or state["skips"] >= 2:
        return None
    result = deepcopy(state)
    result.update(phase="preparing", word=None, skips=state["skips"] + 1)
    result["last_result"] = {"kind": "skip"}
    return result


def timeout(state, next_host):
    result = deepcopy(state)
    result["last_result"] = {"kind": "timeout", "word": state["word"]}
    result.update(
        phase="done" if state["round"] == 10 else "preparing",
        host=next_host,
        word=None,
        round=state["round"] + 1,
        skips=0,
        end_at=None,
    )
    return result
