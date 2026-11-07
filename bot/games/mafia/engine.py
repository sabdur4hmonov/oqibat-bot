"""Pure Mafia actions, phase resolution, safety caps and point rules."""

import random
from collections import Counter
from copy import deepcopy
from datetime import datetime

from bot.games.mafia.roles import COMMISSIONER, DOCTOR, MAFIA, assign, distribution
from bot.services.points import MAFIA_SURVIVED, MAFIA_WIN

MAX_ROUNDS = 20
PHASE_SECONDS = {"night": 60, "discussion": 90, "vote": 60}


def start(lobby: dict, now: datetime, rng=None, roles=None) -> dict:
    result = deepcopy(lobby)
    roles = roles or assign(lobby["players"], rng)
    if set(roles) != set(lobby["players"]) or Counter(roles.values()) != Counter(
        distribution(len(roles))
    ):
        raise ValueError("Invalid Mafia roles")
    result.update(
        phase="night",
        round=1,
        roles=dict(roles),
        alive=list(lobby["players"]),
        night={"mafia": {}, "doctor": None, "check": None},
        votes={},
        last_doctor_self=False,
        last_event=None,
        winner=None,
    )
    return result


def winner(state) -> str | None:
    mafia = sum(state["roles"][user] == MAFIA for user in state["alive"])
    others = len(state["alive"]) - mafia
    return "town" if mafia == 0 else "mafia" if mafia >= others else None


def action(state, actor: int, operation: str, target: int) -> dict | None:
    actor, target = str(actor), str(target)
    if actor not in state.get("alive", []) or target not in state["alive"]:
        return None
    result = deepcopy(state)
    role = state["roles"][actor]
    if state["phase"] == "vote" and operation == "v":
        result["votes"][actor] = target
    elif state["phase"] == "night":
        if operation == "m" and role == MAFIA and state["roles"][target] != MAFIA:
            result["night"]["mafia"][actor] = target
        elif operation == "d" and role == DOCTOR:
            if actor == target and state["last_doctor_self"]:
                return None
            result["night"]["doctor"] = target
        elif (
            operation == "c"
            and role == COMMISSIONER
            and actor != target
            and state["night"]["check"] is None
        ):
            result["night"]["check"] = target
        else:
            return None
    else:
        return None
    return result


def tally(state, *, mafia=False) -> dict[str, int]:
    votes = state["night"]["mafia"] if mafia else state["votes"]
    return dict(
        Counter(
            target
            for user, target in votes.items()
            if user in state["alive"]
            and target in state["alive"]
            and (not mafia or state["roles"][user] == MAFIA)
        )
    )


def finish(state, outcome):
    result = deepcopy(state)
    result.update(
        phase="done", winner=outcome, votes={}, night={"mafia": {}, "doctor": None, "check": None}
    )
    return result


def advance(state, now: datetime, rng=None) -> dict:
    if state.get("phase") == "done":
        return deepcopy(state)
    if now >= datetime.fromisoformat(state["hard_deadline"]) or state["round"] > MAX_ROUNDS:
        return finish(state, "draw")
    result = deepcopy(state)
    phase = state["phase"]
    if phase == "discussion":
        result.update(phase="vote", votes={})
        return result
    if phase not in {"night", "vote"}:
        raise ValueError("Not an active Mafia phase")
    counts = tally(state, mafia=phase == "night")
    tied = (
        [user for user, votes in counts.items() if votes == max(counts.values())] if counts else []
    )
    victim = (
        (rng or random).choice(sorted(tied))
        if tied and (phase == "night" or len(tied) == 1)
        else None
    )
    saved = phase == "night" and victim is not None and victim == state["night"]["doctor"]
    if phase == "night":
        doctor = next((user for user, role in state["roles"].items() if role == DOCTOR), None)
        result["last_doctor_self"] = bool(doctor and doctor == state["night"]["doctor"])
    if saved:
        victim = None
    if victim is not None:
        result["alive"].remove(victim)
    result["last_event"] = {
        "kind": phase,
        "victim": victim,
        "role": state["roles"].get(victim),
        "saved": saved,
        "tie": phase == "vote" and len(tied) > 1,
    }
    result.update(votes={}, night={"mafia": {}, "doctor": None, "check": None})
    outcome = winner(result)
    if outcome:
        return finish(result, outcome)
    if phase == "vote":
        if state["round"] >= MAX_ROUNDS:
            return finish(result, "draw")
        result.update(phase="night", round=state["round"] + 1)
    else:
        result["phase"] = "discussion"
    return result


def awards(state) -> list[tuple[int, int, str]]:
    if state.get("phase") != "done" or state.get("winner") not in {"town", "mafia", "draw"}:
        return []
    result = []
    for user, role in state["roles"].items():
        if user in state.get("forfeited", []):
            continue
        side = "mafia" if role == MAFIA else "town"
        if side == state["winner"]:
            result.append((int(user), MAFIA_WIN, "mafia_win"))
        if user in state["alive"]:
            result.append((int(user), MAFIA_SURVIVED, "mafia_survived"))
    return result


def forfeit(state, user):
    user = str(user)
    if user not in state.get("alive", []):
        return None
    result = deepcopy(state)
    result["alive"].remove(user)
    result.setdefault("forfeited", []).append(user)
    result["votes"] = {
        voter: target
        for voter, target in state["votes"].items()
        if voter != user and target != user
    }
    result["night"]["mafia"] = {
        voter: target
        for voter, target in state["night"]["mafia"].items()
        if voter != user and target != user
    }
    for field in ("doctor", "check"):
        actor_role = DOCTOR if field == "doctor" else COMMISSIONER
        if result["night"][field] == user or state["roles"][user] == actor_role:
            result["night"][field] = None
    result["last_event"] = {"kind": "left", "victim": user, "role": state["roles"][user]}
    outcome = winner(result)
    return finish(result, outcome) if outcome else result
