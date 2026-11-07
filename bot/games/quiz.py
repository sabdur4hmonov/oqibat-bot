"""Pure answer scoring; callers serialize it with the shared chat lock."""

from copy import deepcopy

from bot.services.points import QUIZ_CORRECT, QUIZ_FIRST_BONUS


def answer(state: dict, user_id: int, name: str, choices: list[int]) -> tuple[dict, int]:
    state = deepcopy(state)
    key = str(user_id)
    if state.get("phase") != "question" or key in state.get("answered", {}):
        return state, 0
    state.setdefault("answered", {})[key] = choices
    state.setdefault("names", {})[key] = name
    if choices != [state["correct"]]:
        return state, 0
    delta = QUIZ_CORRECT
    if state.get("first_correct") is None:
        state["first_correct"] = user_id
        delta += QUIZ_FIRST_BONUS
    scores = state.setdefault("scores", {})
    scores[key] = scores.get(key, 0) + delta
    return state, delta
