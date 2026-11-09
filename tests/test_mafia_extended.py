import random
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.methods import AnswerCallbackQuery, EditMessageText
from test_easy_games import game_app as game_app
from test_group_flows import callback
from test_mafia_flows import action, advance, lobby

from bot import texts
from bot.games.mafia import engine
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

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def start(count=11, seed=None):
    players = {str(user): f"User {user}" for user in range(1, count + 1)}
    roles = (
        assign(players, random.Random(seed), extended=True)
        if seed is not None
        else dict(zip(players, distribution(count, True), strict=True))
    )
    return engine.start(
        {
            "players": players,
            "extended_roles": True,
            "hard_deadline": (NOW + timedelta(hours=1)).isoformat(),
        },
        NOW,
        roles=roles,
    )


def choose(state, actor, operation, target):
    result = engine.action(state, int(actor), operation, int(target))
    assert result is not None
    return result


def night(state, target=None, serial=None, block=None, doctor=None):
    assert state["phase"] == "night"
    if target:
        for user in state["alive"]:
            if is_mafia(state["roles"][user]):
                state = choose(state, user, "m", target)
    for role, op, target in ((SERIAL, "s", serial), (MISTRESS, "b", block), (DOCTOR, "d", doctor)):
        if target:
            actor = next(user for user in state["alive"] if state["roles"][user] == role)
            state = choose(state, actor, op, target)
    return engine.advance(state, NOW, random.Random(42))


def day(state, target):
    state = engine.advance(state, NOW)
    assert state["phase"] == "vote"
    for user in state["alive"]:
        state = choose(state, user, "v", target)
    return engine.advance(state, NOW)


@pytest.mark.parametrize("count", range(5, 16))
def test_extended_thresholds_keep_base_mafia_team_size(count):
    state = start(count)
    counts = Counter(state["roles"].values())
    assert counts[DON] == int(count >= 8)
    assert counts[MISTRESS] == int(count >= 9)
    assert counts[SERIAL] == int(count >= 11)
    assert counts[MAFIA] + counts[DON] == (1 if count <= 6 else 2 if count <= 9 else 3)
    assert counts[DOCTOR] == counts[COMMISSIONER] == 1
    assert Counter(assign(state["players"], extended=True).values()) == counts


def test_scripted_full_extended_town_win():
    state = start()
    for target in ("1", "2", "3", "7"):
        state = night(state)
        state = day(state, target)
    assert state["phase"] == "done" and state["winner"] == "town"
    assert all(
        side(state["roles"][str(user)]) == "town"
        for user, _, reason in engine.awards(state)
        if reason == "mafia_win"
    )


def test_scripted_full_extended_mafia_win():
    state = night(start(), "7", block="4", doctor="7")
    assert "7" not in state["alive"]  # block cancels the doctor's save
    state = day(state, "8")
    state = night(state, "9")
    state = day(state, "10")
    state = night(state, "11")
    assert state["winner"] == "mafia"
    assert {user for user, _, reason in engine.awards(state) if reason == "mafia_win"} == {1, 2, 3}


def test_scripted_full_extended_manyak_win():
    state = night(start(), "8", serial="9")
    assert set(state["last_event"]["victims"]) == {"8", "9"}
    state = day(state, "1")
    state = night(state, "10", serial="11")
    state = day(state, "2")
    state = night(state, "4", serial="5")
    state = day(state, "6")
    assert state["winner"] == "manyak" and set(state["alive"]) == {"3", "7"}
    assert (7, 10, "mafia_win") in engine.awards(state)


def test_don_tie_and_blocked_don_vote():
    state = choose(start(), "1", "m", "8")
    state = choose(state, "2", "m", "9")
    assert engine.advance(state, NOW)["last_event"]["victim"] == "8"
    blocked = choose(state, "6", "b", "1")
    assert engine.advance(blocked, NOW)["last_event"]["victim"] == "9"


def test_block_repeat_guard_doctor_self_and_simultaneous_save():
    state = night(start(), "8", serial="8", doctor="8")
    assert state["last_event"]["saved"] and not state["last_event"]["victims"]
    state = night(start(), "4", serial="8", doctor="8")
    assert "4" not in state["alive"] and "8" in state["alive"]
    assert state["last_event"]["saved"]
    state = night(start(), "8", block="4", doctor="4")
    assert not state["last_doctor_self"]
    state = day(state, "9")
    assert engine.action(state, 6, "b", 4) is None
    assert engine.action(state, 4, "d", 4) is not None


def test_blocked_manyak_and_commissioner_and_don_disguise():
    state = night(start(), serial="8", block="7")
    assert "8" in state["alive"]
    state = choose(start(), "5", "c", "2")
    state = choose(state, "6", "b", "5")
    assert engine.advance(state, NOW)["last_check"]["is_mafia"] is None
    state = choose(start(), "5", "c", "1")
    assert engine.advance(state, NOW)["last_check"]["is_mafia"] is False


def test_winner_precedence_and_forfeit_clears_new_actions():
    state = start()
    state["alive"] = ["1", "7"]
    assert engine.winner(state) == "manyak"
    state["alive"] = ["1", "2", "4", "5", "7"]
    assert engine.winner(state) is None  # living manyak prevents mafia parity victory
    state["alive"] = ["4", "7"]
    assert engine.winner(state) == "manyak"
    state = choose(start(), "7", "s", "8")
    assert engine.forfeit(state, 7)["night"]["serial"] is None
    state = choose(start(), "6", "b", "8")
    assert engine.forfeit(state, 6)["night"]["block"] is None


def test_fuzz_1000_extended_games_end_with_valid_roles_winners_and_dead_guards():
    outcomes = Counter()
    for seed in range(1000):
        rng = random.Random(seed)
        count = rng.randint(5, 15)
        state = start(count, seed)
        original_roles = dict(state["roles"])
        now = NOW
        for _ in range(61):
            if state["phase"] == "done":
                break
            prior = set(state["alive"])
            for user in state["players"]:
                target = int(rng.choice(state["alive"]))
                if user not in state["alive"]:
                    before = deepcopy(state)
                    for operation in "mdcvbs":
                        assert engine.action(state, int(user), operation, target) is None
                    assert state == before
                elif rng.random() < 0.8:
                    operation = (
                        "v"
                        if state["phase"] == "vote"
                        else {
                            MAFIA: "m",
                            DON: "m",
                            DOCTOR: "d",
                            COMMISSIONER: "c",
                            MISTRESS: "b",
                            SERIAL: "s",
                        }.get(state["roles"][user], "x")
                    )
                    changed = engine.action(state, int(user), operation, target)
                    if changed is not None:
                        state = changed
            now += timedelta(seconds=engine.PHASE_SECONDS[state["phase"]])
            state = engine.advance(state, now, rng)
            assert set(state["alive"]) <= prior
            assert state["roles"] == original_roles
            assert Counter(state["roles"].values()) == Counter(distribution(count, True))
            assert set(state["votes"]) <= set(state["alive"])
            assert set(state["night"]["mafia"]) <= set(state["alive"])
            assert state["round"] <= 20
        assert state["phase"] == "done"
        assert state["winner"] in {"town", "mafia", "manyak", "draw"}
        outcomes[state["winner"]] += 1
    assert outcomes["town"] and outcomes["mafia"] and outcomes["manyak"]


async def test_extended_setting_snapshot_private_block_and_deferred_check(game_app):
    feed, transport, runtime = game_app
    assert not (await runtime.groups.get(-1)).extended_roles
    await feed(callback("sv:extended_roles:1"))
    game = await lobby(game_app, 11)
    assert game.state["extended_roles"]
    await feed(callback("sv:extended_roles:0"))
    game = await advance(game_app)
    assert game.state["extended_roles"] and SERIAL in game.state["roles"].values()
    cop = next(user for user, role in game.state["roles"].items() if role == COMMISSIONER)
    blocker = next(user for user, role in game.state["roles"].items() if role == MISTRESS)
    mafia = next(user for user, role in game.state["roles"].items() if role == MAFIA)
    await feed(action(game, blocker, "b", cop))
    await feed(action(game, cop, "c", mafia))
    alerts = [item for item in transport.methods if isinstance(item, AnswerCallbackQuery)]
    assert alerts[-1].text == texts.MAFIA_CHECK_AT_DAWN
    await advance(game_app)
    updates = [
        item
        for item in transport.methods
        if isinstance(item, EditMessageText) and item.chat_id == int(cop)
    ]
    assert "to‘sildi" in updates[-1].text
    await feed(action(game, cop, "c", mafia, round_number=0))
    alerts = [item for item in transport.methods if isinstance(item, AnswerCallbackQuery)]
    assert alerts[-1].text == texts.MAFIA_STALE
