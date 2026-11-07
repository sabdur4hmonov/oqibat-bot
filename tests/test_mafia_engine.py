import random
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from bot.games.mafia import engine
from bot.games.mafia.roles import COMMISSIONER, DOCTOR, MAFIA, TOWN, assign, distribution

NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)


def game(count=5, seed=1):
    lobby = {
        "players": {str(user): f"User {user}" for user in range(1, count + 1)},
        "hard_deadline": (NOW + timedelta(minutes=60)).isoformat(),
    }
    return engine.start(lobby, NOW, random.Random(seed))


@pytest.mark.parametrize("count", range(5, 16))
def test_role_distribution_is_exact_and_assignment_unique(count):
    roles = assign(range(1, count + 1), random.Random(count))
    expected = 1 if count <= 6 else 2 if count <= 9 else 3
    assert Counter(roles.values()) == {
        MAFIA: expected,
        DOCTOR: 1,
        COMMISSIONER: 1,
        TOWN: count - expected - 2,
    }
    assert len(roles) == count
    for bad in (4, 16):
        with pytest.raises(ValueError):
            distribution(bad)
    with pytest.raises(ValueError):
        assign([1, 1, 2, 3, 4])


def role_user(state, role):
    return next(user for user, value in state["roles"].items() if value == role)


def test_full_scripted_town_win_and_points():
    state = game()
    mafia = role_user(state, MAFIA)
    original = deepcopy(state)
    state = engine.advance(state, NOW)  # no mafia vote = no kill
    assert len(state["alive"]) == 5 and not state["last_event"]["saved"]
    assert original["phase"] == "night"
    state = engine.advance(state, NOW)
    for user in state["alive"]:
        state = engine.action(state, int(user), "v", int(mafia))
    state = engine.advance(state, NOW)
    assert state["winner"] == "town" and mafia not in state["alive"]
    assert sum(delta for _, delta, _ in engine.awards(state)) == 52
    assert engine.action(state, int(mafia), "m", 2) is None


def test_full_scripted_mafia_win():
    state = game()
    mafia = role_user(state, MAFIA)
    towns = [user for user, role in state["roles"].items() if role == TOWN]
    state = engine.action(state, int(mafia), "m", int(towns[0]))
    state = engine.advance(state, NOW)
    assert state["last_event"]["role"] == TOWN
    state = engine.advance(state, NOW)
    for user in list(state["alive"]):
        state = engine.action(state, int(user), "v", int(towns[1]))
    state = engine.advance(state, NOW)
    assert state["round"] == 2 and state["phase"] == "night"
    victim = role_user(state, DOCTOR)
    state = engine.action(state, int(mafia), "m", int(victim))
    state = engine.advance(state, NOW)
    assert state["winner"] == "mafia" and len(state["alive"]) == 2
    assert (int(mafia), 10, "mafia_win") in engine.awards(state)


def test_doctor_no_consecutive_self_commissioner_once_and_dead_cannot_act():
    state = game()
    mafia, doctor, cop = [role_user(state, role) for role in (MAFIA, DOCTOR, COMMISSIONER)]
    state = engine.action(state, int(mafia), "m", int(doctor))
    state = engine.action(state, int(doctor), "d", int(doctor))
    state = engine.action(state, int(cop), "c", int(mafia))
    assert engine.action(state, int(cop), "c", int(doctor)) is None
    state = engine.advance(state, NOW)
    assert state["last_event"]["saved"] and doctor in state["alive"]
    state = engine.advance(state, NOW)
    state = engine.advance(state, NOW)  # no day votes
    assert engine.action(state, int(doctor), "d", int(doctor)) is None
    state = engine.action(state, int(mafia), "m", int(cop))
    state = engine.advance(state, NOW)
    assert cop not in state["alive"]
    assert engine.action(state, int(cop), "c", int(mafia)) is None
    state = engine.advance(state, NOW)
    assert engine.action(state, int(cop), "v", int(mafia)) is None


def test_mafia_ties_choose_tied_target_day_ties_eliminate_nobody_and_votes_change():
    state = game(7)
    mafias = [user for user, role in state["roles"].items() if role == MAFIA]
    targets = [user for user, role in state["roles"].items() if role != MAFIA][:2]
    for user, target in zip(mafias, targets, strict=True):
        state = engine.action(state, int(user), "m", int(target))
    resolved = engine.advance(state, NOW, random.Random(1))
    assert resolved["last_event"]["victim"] in targets
    vote = engine.advance(resolved, NOW)
    a, b = vote["alive"][:2]
    vote = engine.action(vote, int(a), "v", int(a))
    vote = engine.action(vote, int(a), "v", int(b))
    assert engine.tally(vote) == {b: 1}
    vote = engine.action(vote, int(b), "v", int(a))
    next_night = engine.advance(vote, NOW)
    assert next_night["last_event"]["tie"] and next_night["alive"] == vote["alive"]


def test_both_caps_and_forfeit_are_pure_and_end_safely():
    state = game()
    assert engine.advance(state, NOW + timedelta(minutes=60))["winner"] == "draw"
    for _ in range(60):
        state = engine.advance(state, NOW)
        if state["phase"] == "done":
            break
    assert state["winner"] == "draw" and state["round"] == 20
    state = game()
    mafia = role_user(state, MAFIA)
    changed = engine.forfeit(state, mafia)
    assert mafia in state["alive"] and mafia not in changed["alive"]
    assert changed["winner"] == "town"
    assert all(user != int(mafia) for user, _, _ in engine.awards(changed))
    state = game()
    doctor = role_user(state, DOCTOR)
    other = next(user for user in state["alive"] if user != doctor)
    state = engine.action(state, int(doctor), "d", int(other))
    assert engine.forfeit(state, doctor)["night"]["doctor"] is None


def test_fuzz_1000_games_always_finish_and_preserve_invariants():
    outcomes = Counter()
    for seed in range(1000):
        rng = random.Random(seed)
        state = game(rng.randint(5, 15), seed)
        original_roles = dict(state["roles"])
        for _ in range(61):
            if state["phase"] == "done":
                break
            previous_alive = set(state["alive"])
            for user in list(state["players"]):
                target = int(rng.choice(state["alive"]))
                if user not in state["alive"]:
                    before = deepcopy(state)
                    for operation in "mdcv":
                        assert engine.action(state, int(user), operation, target) is None
                    assert state == before
                elif rng.random() < 0.8:
                    operation = (
                        "v"
                        if state["phase"] == "vote"
                        else {MAFIA: "m", DOCTOR: "d", COMMISSIONER: "c"}.get(
                            state["roles"][user], "x"
                        )
                    )
                    changed = engine.action(state, int(user), operation, target)
                    if changed is not None:
                        state = changed
            state = engine.advance(state, NOW, rng)
            assert set(state["alive"]) <= previous_alive
            assert state["roles"] == original_roles
            assert Counter(state["roles"].values()) == Counter(distribution(len(state["players"])))
            assert set(state["votes"]) <= set(state["alive"])
            assert state["round"] <= 20
        assert state["phase"] == "done"
        assert state["winner"] in {"town", "mafia", "draw"}
        outcomes[state["winner"]] += 1
    assert outcomes["town"] and outcomes["mafia"]
