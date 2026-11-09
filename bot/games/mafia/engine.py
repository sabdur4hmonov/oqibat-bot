"""Pure Mafia actions, phase resolution, safety caps and point rules."""

import random
from collections import Counter
from copy import deepcopy
from datetime import datetime

from bot.games.mafia.roles import (
    COMMISSIONER,
    DOCTOR,
    DON,
    MAFIA,
    MISTRESS,
    SERIAL,
    assign,
    distribution,
    is_mafia,
    side,
)
from bot.services.points import MAFIA_SURVIVED, MAFIA_WIN

MAX_ROUNDS = 20
PHASE_SECONDS = {"night": 60, "discussion": 90, "vote": 60}


def empty_night(state):
    result = {"mafia": {}, "doctor": None, "check": None}
    if state.get("extended_roles"):
        result.update(block=None, serial=None)
    return result


def start(lobby: dict, now: datetime, rng=None, roles=None) -> dict:
    result = deepcopy(lobby)
    extended = lobby.get("extended_roles", False)
    roles = roles or assign(lobby["players"], rng, extended=extended)
    if set(roles) != set(lobby["players"]) or Counter(roles.values()) != Counter(
        distribution(len(roles), extended)
    ):
        raise ValueError("Invalid Mafia roles")
    result.update(
        phase="night",
        round=1,
        roles=dict(roles),
        alive=list(lobby["players"]),
        night=empty_night(lobby),
        votes={},
        last_doctor_self=False,
        last_event=None,
        winner=None,
        last_block=None,
        last_check=None,
    )
    return result


def winner(state) -> str | None:
    mafia = sum(is_mafia(state["roles"][user]) for user in state["alive"])
    serial = any(state["roles"][user] == SERIAL for user in state["alive"])
    others = len(state["alive"]) - mafia
    if serial and len(state["alive"]) <= 2:
        return "manyak"
    if mafia == 0 and not serial:
        return "town"
    return "mafia" if not serial and mafia >= others else None


def action(state, actor: int, operation: str, target: int) -> dict | None:
    actor, target = str(actor), str(target)
    if actor not in state.get("alive", []) or target not in state["alive"]:
        return None
    result = deepcopy(state)
    role = state["roles"][actor]
    if state["phase"] == "vote" and operation == "v":
        result["votes"][actor] = target
    elif state["phase"] == "night":
        if operation == "m" and is_mafia(role) and not is_mafia(state["roles"][target]):
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
        elif (
            operation == "b"
            and role == MISTRESS
            and actor != target
            and target != state.get("last_block")
        ):
            result["night"]["block"] = target
        elif operation == "s" and role == SERIAL and actor != target:
            result["night"]["serial"] = target
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
            and (not mafia or is_mafia(state["roles"][user]))
        )
    )


def finish(state, outcome):
    result = deepcopy(state)
    result.update(phase="done", winner=outcome, votes={}, night=empty_night(state))
    return result


def advance(state, now: datetime, rng=None) -> dict:
    if state.get("phase") == "done":
        return deepcopy(state)
    if now >= datetime.fromisoformat(state["hard_deadline"]) or state["round"] > MAX_ROUNDS:
        return finish(state, "draw")
    result = deepcopy(state)
    phase = state["phase"]
    if phase == "night" and state.get("extended_roles"):
        return extended_night(state, rng)
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
    result.update(votes={}, night=empty_night(state))
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
    if state.get("phase") != "done" or state.get("winner") not in {
        "town",
        "mafia",
        "manyak",
        "draw",
    }:
        return []
    result = []
    for user, role in state["roles"].items():
        if user in state.get("forfeited", []):
            continue
        if side(role) == state["winner"]:
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
    for field, actor_role in (
        ("doctor", DOCTOR),
        ("check", COMMISSIONER),
        ("block", MISTRESS),
        ("serial", SERIAL),
    ):
        if field in result["night"] and (
            result["night"][field] == user or state["roles"][user] == actor_role
        ):
            result["night"][field] = None
    result["last_event"] = {"kind": "left", "victim": user, "role": state["roles"][user]}
    outcome = winner(result)
    return finish(result, outcome) if outcome else result


def extended_night(state, rng=None):
    """Block first; simultaneous attacks/saves/check; then winner evaluation."""
    result = deepcopy(state)
    alive = state["alive"]
    actors = {
        role: next((user for user in alive if state["roles"][user] == role), None)
        for role in (DON, DOCTOR, COMMISSIONER, MISTRESS, SERIAL)
    }
    blocked = state["night"].get("block") if actors[MISTRESS] else None
    blocked = blocked if blocked in alive else None
    result["night"]["mafia"] = {
        user: target
        for user, target in state["night"]["mafia"].items()
        if user != blocked and user in alive and target in alive
    }
    counts = tally(result, mafia=True)
    tied = (
        [user for user, count in counts.items() if count == max(counts.values())] if counts else []
    )
    don_target = result["night"]["mafia"].get(actors[DON])
    mafia_victim = (
        (don_target if don_target in tied else (rng or random).choice(sorted(tied)))
        if tied
        else None
    )
    doctor = actors[DOCTOR]
    saved_target = state["night"]["doctor"] if doctor and doctor != blocked else None
    serial = actors[SERIAL]
    serial_victim = state["night"].get("serial") if serial and serial != blocked else None
    attacked = {target for target in (mafia_victim, serial_victim) if target in alive}
    victims = sorted(attacked - {saved_target})
    result["alive"] = [user for user in alive if user not in victims]
    result["last_doctor_self"] = bool(doctor and doctor == saved_target)
    result["last_block"] = blocked
    cop, checked = actors[COMMISSIONER], state["night"]["check"]
    if cop and checked in alive:
        result["last_check"] = {
            "actor": cop,
            "target": checked,
            "round": state["round"],
            "is_mafia": None if cop == blocked else state["roles"][checked] == MAFIA,
        }
    result["last_event"] = {
        "kind": "night",
        "victims": victims,
        "victim": victims[0] if victims else None,
        "role": state["roles"][victims[0]] if victims else None,
        "saved": saved_target in attacked,
        "tie": False,
    }
    result.update(votes={}, night=empty_night(state))
    outcome = winner(result)
    if outcome:
        return finish(result, outcome)
    result["phase"] = "discussion"
    return result
