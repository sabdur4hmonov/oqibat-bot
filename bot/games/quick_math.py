"""Generated integer arithmetic and pure first-correct-per-round scoring."""

from copy import deepcopy

ROUNDS = 5
MAX_ATTEMPTS = 500


def evaluate(a, operation, b):
    if operation == "+":
        return a + b
    if operation == "-":
        return a - b
    if operation == "*":
        return a * b
    raise ValueError("Invalid operation")


def questions(rng):
    pool = {}
    for operation in ("+", "-", "*"):
        for a in range(1, 13):
            for b in range(1, 13):
                answer = evaluate(a, operation, b)
                if answer >= 0:
                    pool.setdefault(answer, []).append((a, operation, b))
    result = []
    for answer in rng.sample(sorted(pool), ROUNDS):
        a, operation, b = rng.choice(pool[answer])
        options = rng.sample([n for n in range(max(0, answer - 10), answer + 11) if n != answer], 3)
        options.append(answer)
        rng.shuffle(options)
        result.append(
            {"a": a, "op": operation, "b": b, "options": options, "correct": options.index(answer)}
        )
    return result


def initial(items):
    if len(items) != ROUNDS:
        raise ValueError("Five questions required")
    return {
        "phase": "preparing",
        "round": 1,
        "questions": deepcopy(items),
        "attempted": [],
        "names": {},
        "scores": {},
        "last_result": None,
    }


def next_round(state, winner=None):
    result = deepcopy(state)
    item = state["questions"][state["round"] - 1]
    result["last_result"] = {
        "a": item["a"],
        "op": item["op"],
        "b": item["b"],
        "answer": item["options"][item["correct"]],
        "winner": winner,
    }
    result["attempted"] = []
    if state["round"] == ROUNDS:
        result["phase"] = "done"
    else:
        result.update(phase="preparing", round=state["round"] + 1)
    return result


def answer(state, user, name, option, round_number):
    if (
        state.get("phase") != "playing"
        or round_number != state["round"]
        or type(user) is not int
        or user <= 0
        or type(option) is not int
        or not 0 <= option < 4
        or str(user) in state["attempted"]
        or len(state["attempted"]) >= MAX_ATTEMPTS
    ):
        return None
    result = deepcopy(state)
    result["attempted"].append(str(user))
    correct = option == state["questions"][state["round"] - 1]["correct"]
    if correct:
        result["names"][str(user)] = name
        result["scores"][str(user)] = result["scores"].get(str(user), 0) + 2
        result = next_round(result, user)
    return result, correct
