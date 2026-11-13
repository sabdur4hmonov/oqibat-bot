import asyncio
import random
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

import pytest
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from sqlalchemy import event, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games import number_hunt, quick_math
from bot.services.quick_games import math_keyboard
from bot.services.sender import Priority
from bot.utils.time import utc_now


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", 1),
        (" 100 ", 100),
        ("001", 1),
        ("101", None),
        ("0", None),
        ("-1", None),
        ("50.0", None),
        ("５０", None),
        ("five", None),
        (None, None),
        ("9" * 10000, None),
    ],
)
def test_number_parser_bounded_ascii(value, expected):
    assert number_hunt.parse_guess(value) == expected


def test_number_hints_immutable_replays_cooldown_and_limits():
    state = number_hunt.initial(60) | {"phase": "playing", "last_message_id": 100}
    original = deepcopy(state)
    first = number_hunt.guess(state, 1, "<A>", 20, 101, 100)
    assert state == original and first["low"] == 21 and first["high"] == 100
    assert first["hint"] == "higher" and first["attempts"] == 1
    assert number_hunt.guess(first, 1, "A", 60, 102, 102.9) is None
    assert number_hunt.guess(first, 2, "B", 60, 101, 104) is None
    assert number_hunt.guess(first, 2, "B", 20, 102, 104) is None
    second = number_hunt.guess(first, 1, "A", 80, 102, 103)
    assert second["high"] == 79 and second["hint"] == "lower"
    final = number_hunt.guess(second, 2, "B", 60, 103, 103)
    assert final["winner"] == 2 and final["scores"] == {"2": 3}
    assert number_hunt.guess(final, 1, "A", 60, 104, 110) is None
    assert number_hunt.expire(first)["result"] == "timeout"
    state = number_hunt.initial(100) | {"phase": "playing"}
    for i in range(1, 16):
        state = number_hunt.guess(state, 1, "A", i, i, i * 3)
    assert state["phase"] == "done" and state["result"] == "limit" and not state["scores"]
    for bad in (0, 101, True):
        with pytest.raises(ValueError):
            number_hunt.initial(bad)


def test_every_number_is_reachable_with_finite_binary_search():
    for secret in range(1, 101):
        state = number_hunt.initial(secret) | {"phase": "playing"}
        for attempt in range(1, 8):
            guess = (state["low"] + state["high"]) // 2
            state = number_hunt.guess(state, 1, "A", guess, attempt, attempt * 3)
            assert state["low"] <= secret <= state["high"]
            if state["phase"] == "done":
                break
        assert state["winner"] == 1 and state["scores"] == {"1": 3}


def test_generated_maths_options_unique_answers_and_all_operations():
    operations = set()
    for seed in range(200):
        items = quick_math.questions(random.Random(seed))
        assert len(items) == 5
        answers = []
        for item in items:
            answer = quick_math.evaluate(item["a"], item["op"], item["b"])
            assert item["options"][item["correct"]] == answer
            assert len(set(item["options"])) == 4 and min(item["options"]) >= 0
            answers.append(answer)
            operations.add(item["op"])
        assert len(set(answers)) == 5
    assert operations == {"+", "-", "*"}
    with pytest.raises(ValueError):
        quick_math.evaluate(1, "/", 0)
    with pytest.raises(ValueError):
        quick_math.initial([])


def test_math_one_attempt_cap_rounds_scores_timeouts_and_purity():
    state = quick_math.initial(quick_math.questions(random.Random(3))) | {"phase": "playing"}
    original = deepcopy(state)
    correct = state["questions"][0]["correct"]
    wrong, ok = quick_math.answer(state, 1, "A", (correct + 1) % 4, 1)
    assert not ok and state == original
    assert quick_math.answer(wrong, 1, "A", correct, 1) is None
    capped = state | {"attempted": [str(i) for i in range(1, 501)]}
    assert quick_math.answer(capped, 501, "A", correct, 1) is None
    assert quick_math.answer(state, True, "A", correct, 1) is None
    assert quick_math.answer(state, 2, "A", correct, 2) is None
    for round_number in range(1, 6):
        state["phase"] = "playing"
        state, ok = quick_math.answer(
            state, 2, "B", state["questions"][round_number - 1]["correct"], round_number
        )
        assert ok and state["last_result"]["winner"] == 2
    assert state["phase"] == "done" and state["scores"] == {"2": 10}
    assert quick_math.answer(state, 1, "A", 0, 5) is None
    state = original
    for _ in range(5):
        state = quick_math.next_round(state)
    assert state["phase"] == "done" and not state["scores"]


async def start(app, kind):
    feed, _, runtime = app
    await feed(command_update("/sontop" if kind == "number" else "/matematika"))
    return runtime.game_cache.main(-1)


def number_message(value, message_id=101, user=2, board_id=100):
    update = command_update(str(value), message_id=message_id, user_id=user)
    reply = command_update("board", message_id=board_id).message
    return update.model_copy(
        update={"message": update.message.model_copy(update={"reply_to_message": reply})}
    )


async def tap(app, game, user, option, round_number=None):
    feed, _, runtime = app
    await feed(callback(f"qm:{game.id}:{round_number or game.state['round']}:{option}", user))
    await runtime.effects.drain()


async def ledger(sessions):
    async with sessions() as session:
        return (await session.scalars(select(PointEvent).order_by(PointEvent.id))).all()


async def test_number_complete_reply_hints_winner_dedup_escaped_card_and_priority(
    game_app, sessions
):
    feed, transport, runtime = game_app
    with (
        patch.object(runtime.quick_games.rng, "randint", return_value=60),
        patch.object(runtime.sender, "send", wraps=runtime.sender.send) as sends,
    ):
        game = await start(game_app, "number")
        assert game.state["phase"] == "playing"
        assert game.phase_deadline_at > utc_now() + timedelta(seconds=175)
        await feed(number_message(20))
        await runtime.effects.drain()
        board = [m for m in transport.methods if isinstance(m, EditMessageText)][-1]
        assert "21–100" in board.text and "kattaroq" in board.text
        assert "Son: 60" not in board.text
        await feed(number_message(60, 102, 3))
        await runtime.effects.drain()
        assert runtime.game_cache.main(-1) is None
        final = [m for m in transport.methods if isinstance(m, EditMessageText)][-1]
        assert "Son: 60" in final.text and "&lt;Sinov&gt;" in final.text
        await feed(number_message(60, 102, 3))
        assert len(await ledger(sessions)) == 1 and (await runtime.points.stats(-1, 3))[0] == 3
        assert all(call.kwargs["priority"] == Priority.GAME for call in sends.call_args_list)
        async with sessions() as session:
            row = await session.get(GameSession, game.id)
            assert texts.game_card_data(row)["rows"] == [("<Sinov>", 3)]


async def test_number_concurrent_correct_messages_award_one_player(game_app, sessions):
    feed, _, runtime = game_app
    game = await start(game_app, "number")
    await asyncio.gather(
        *(feed(number_message(game.state["secret"], 101 + i, 2 + i % 2)) for i in range(10))
    )
    await runtime.effects.drain()
    events = await ledger(sessions)
    assert len(events) == 1 and events[0].delta == 3


async def test_math_complete_five_rounds_wrong_attempts_stale_buttons_no_double_points(
    game_app, sessions
):
    feed, transport, runtime = game_app
    game = await start(game_app, "math")
    await runtime.effects.drain()
    before = len([m for m in transport.methods if isinstance(m, EditMessageText)])
    for round_number in range(1, 6):
        current = runtime.game_cache.main(-1)
        assert current.state["round"] == round_number and current.state["phase"] == "playing"
        correct = current.state["questions"][round_number - 1]["correct"]
        buttons = math_keyboard(current).inline_keyboard[0]
        assert all(len(button.callback_data.encode()) <= 64 for button in buttons)
        await tap(game_app, current, 3, (correct + 1) % 4)
        assert len([m for m in transport.methods if isinstance(m, EditMessageText)]) == before
        await tap(game_app, current, 3, correct)
        assert transport.methods[-1].text == texts.MATH_ALREADY_TRIED
        await tap(game_app, current, 2, correct)
        # Next question's preparing board, then its confirmed-delivery deadline.
        before += 2 if round_number < 5 else 1
        await tap(game_app, current, 1, correct)
        assert len(await ledger(sessions)) == round_number
    assert runtime.game_cache.main(-1) is None
    assert (await runtime.points.stats(-1, 2))[0] == 10
    final = [m for m in transport.methods if isinstance(m, EditMessageText)][-1]
    assert "5 savol yakunlandi" in final.text and "10 ball" in final.text
    assert "&lt;Sinov&gt;" in final.text
    assert sum(isinstance(m, SendMessage) for m in transport.methods) == 2
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert texts.game_card_data(row)["rows"] == [("<Sinov>", 10)]


async def test_math_simultaneous_correct_and_foreign_outsider_bot_callbacks(game_app, sessions):
    feed, _, runtime = game_app
    game = await start(game_app, "math")
    option = game.state["questions"][0]["correct"]
    for user in (77,):
        await tap(game_app, game, user, option)
    update = callback(f"qm:{game.id}:1:{option}", 2)
    for changed in [
        {"message_id": 999},
        {"chat": update.callback_query.message.chat.model_copy(update={"id": -77})},
    ]:
        query = update.callback_query.model_copy(
            update={"message": update.callback_query.message.model_copy(update=changed)}
        )
        await feed(update.model_copy(update={"callback_query": query}))
    await feed(
        update.model_copy(
            update={
                "callback_query": update.callback_query.model_copy(
                    update={"from_user": tg_user(2, True)}
                )
            }
        )
    )
    assert not await ledger(sessions)
    await asyncio.gather(
        *(feed(callback(f"qm:{game.id}:1:{option}", 1 + i % 3)) for i in range(12))
    )
    await runtime.effects.drain()
    assert len(await ledger(sessions)) == 1 and runtime.game_cache.main(-1).state["round"] == 2


@pytest.mark.parametrize("kind", ["number", "math"])
async def test_ordinary_malformed_forwarded_outsider_messages_do_zero_sql(game_app, sessions, kind):
    _, _, runtime = game_app
    game = await start(game_app, kind)
    statements = []
    engine = sessions.kw["bind"].sync_engine

    def listen(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", listen)
    try:
        for _ in range(100):
            for update in [
                command_update("hello"),
                command_update("50"),
                number_message(101),
                number_message(50, user=77),
            ]:
                await runtime.quick_games.observe(game, update.message)
        forwarded = number_message(50).message.model_copy(
            update={"forward_origin": {"type": "user"}}
        )
        await runtime.quick_games.observe(game, forwarded)
        assert not statements
    finally:
        event.remove(engine, "before_cursor_execute", listen)


@pytest.mark.parametrize("kind", ["number", "math"])
async def test_play_window_starts_only_after_delivery_and_watchdog_is_independent(game_app, kind):
    feed, _, runtime = game_app
    original = runtime.game_hub.board
    started, release = asyncio.Event(), asyncio.Event()
    clock = [utc_now()]

    async def delayed(*args, **kwargs):
        started.set()
        await release.wait()
        return await original(*args, **kwargs)

    with (
        patch.object(runtime.game_hub, "board", side_effect=delayed),
        patch("bot.services.quick_games.utc_now", side_effect=lambda: clock[0]),
    ):
        task = asyncio.create_task(start(game_app, kind))
        await asyncio.wait_for(started.wait(), 2)
        pending = runtime.game_cache.main(-1)
        assert pending.state["phase"] == "preparing"
        clock[0] += timedelta(seconds=50)
        release.set()
        game = await asyncio.wait_for(task, 2)
        assert game.phase_deadline_at == clock[0] + timedelta(
            seconds=180 if kind == "number" else 20
        )
    await feed(command_update("/stop"))
    # A preparation watchdog must end state without waiting on that delayed API.
    state = (
        number_hunt.initial(30)
        if kind == "number"
        else quick_math.initial(quick_math.questions(random.Random(1)))
    )
    game = await runtime.games.start(-1, 1, kind, state, utc_now())
    await asyncio.wait_for(runtime.game_hub.advance(game, game.phase_deadline_at), 2)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None


@pytest.mark.parametrize("kind", ["number", "math"])
async def test_expiry_stop_leave_restart_migration_privacy_and_retained_scores(
    game_app, sessions, kind
):
    feed, _, runtime = game_app
    game = await start(game_app, kind)
    if kind == "math":
        await tap(game_app, game, 2, game.state["questions"][0]["correct"])
        game = runtime.game_cache.main(-1)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    if kind == "number":
        assert runtime.game_cache.main(-1) is None
    else:
        assert runtime.game_cache.main(-1).state["round"] == 3
        assert (await runtime.points.stats(-1, 2))[0] == 2
        await feed(command_update("/stop"))
    game = await start(game_app, kind)
    await feed(command_update("/stop", user_id=3))
    assert runtime.game_cache.main(-1)
    await feed(command_update("/stop", user_id=42))
    assert runtime.game_cache.main(-1) is None
    game = await start(game_app, kind)
    await runtime.game_hub.recover([game])
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    game = await start(game_app, kind)
    await runtime.groups.membership(-1, tg_user(3), opted_in=False)
    assert runtime.game_cache.main(-1)  # another player's exit is harmless
    await runtime.groups.membership(-1, tg_user(1), opted_in=False)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    await runtime.groups.membership(-1, tg_user(1), opted_in=True)
    game = await start(game_app, kind)
    await runtime.migrations.migrate(-1, -10055)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-10055) is None
    message = command_update("/sontop").message
    message = message.model_copy(update={"chat": message.chat.model_copy(update={"id": -10055})})
    await runtime.quick_games.start(message, kind)
    game = runtime.game_cache.main(-10055)
    assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).state == {"erased": True}


async def test_all_math_timeouts_finish_and_global_pause_does_not_delay_state_or_callback(
    game_app, sessions
):
    feed, transport, runtime = game_app
    game = await start(game_app, "math")
    for _ in range(4):
        game = runtime.game_cache.main(-1)
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await runtime.effects.drain()
    final_round = runtime.game_cache.main(-1)

    async def paused(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", paused):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        correct = final_round.state["questions"][4]["correct"]
        await asyncio.wait_for(feed(callback(f"qm:{game.id}:5:{correct}", 2)), 2)
        assert isinstance(transport.methods[-1], AnswerCallbackQuery)
        assert runtime.game_cache.main(-1) is None and len(await ledger(sessions)) == 1


async def test_catalog_private_group_commands_and_main_slot(game_app):
    feed, transport, runtime = game_app
    await feed(command_update("/oyinlar"))
    assert transport.methods[-1].text == texts.HUB_INTRO
    message = command_update("/oyinlar").message
    private = message.model_copy(
        update={"chat": message.chat.model_copy(update={"id": 1, "type": "private"})}
    )
    await feed(command_update("/oyinlar").model_copy(update={"message": private}))
    assert transport.methods[-1].text == texts.HUB_INTRO
    await start(game_app, "number")
    await feed(command_update("/matematika"))
    assert transport.methods[-1].text == texts.GAME_BUSY
    assert "sontop" in texts.GROUP_COMMANDS and "matematika" in texts.GROUP_COMMANDS


@pytest.mark.parametrize("kind", ["number", "math"])
async def test_game_deadline_commits_during_global_pause(game_app, sessions, kind):
    _, _, runtime = game_app
    game = await start(game_app, kind)

    async def paused(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", paused):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        await asyncio.wait_for(runtime.game_hub.advance(game, game.phase_deadline_at), 2)
        async with sessions() as session:
            row = await session.get(GameSession, game.id)
            if kind == "number":
                assert row.status == "finished" and row.state["result"] == "timeout"
            else:
                assert row.state["round"] == 2 and row.state["phase"] == "preparing"
        assert not await ledger(sessions) and runtime.effects.tasks
