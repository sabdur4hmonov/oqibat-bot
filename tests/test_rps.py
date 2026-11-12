import asyncio
from copy import deepcopy
from itertools import product
from unittest.mock import patch

import pytest
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games import rps
from bot.keyboards.rps import game_keyboard
from bot.services.sender import Priority


def lobby():
    return {
        "phase": "lobby",
        "players": [1],
        "names": {"1": "<Ali>"},
        "target": None,
        "choices": {},
        "round": 1,
    }


@pytest.mark.parametrize("first,second", list(product(rps.MOVES, repeat=2)))
def test_all_nine_pairs_and_immutable_hidden_choices(first, second):
    original = lobby()
    state = rps.accept(original, 2, "Vali")
    before = deepcopy(state)
    pending = rps.choose(state, 1, first)
    assert state == before and original == lobby()
    assert pending["phase"] == "choosing" and "winner" not in pending
    final = rps.choose(pending, 2, second)
    expected = (
        None
        if first == second
        else 1
        if (first, second) in {("r", "s"), ("s", "p"), ("p", "r")}
        else 2
    )
    assert final["phase"] == "done" and final["winner"] == expected
    assert pending["choices"] == {"1": first}
    with pytest.raises(ValueError):
        rps.choose(final, 2, "r")


def test_invalid_outsider_duplicate_target_and_lobby_guards():
    state = lobby()
    with pytest.raises(ValueError):
        rps.accept(state, 1, "Self")
    with pytest.raises(ValueError):
        rps.accept(state | {"target": 3}, 2, "Wrong")
    with pytest.raises(ValueError):
        rps.choose(state, 1, "r")
    playing = rps.accept(state, 2, "Second")
    for user, move in [(3, "r"), (True, "r"), (1, "bad")]:
        with pytest.raises(ValueError):
            rps.choose(playing, user, move)
    with pytest.raises(ValueError):
        rps.choose(rps.choose(playing, 1, "p"), 1, "s")
    with pytest.raises(ValueError):
        rps.winner("bad", "r")


async def start(app, *, target=None, command="/tqq"):
    feed, _, runtime = app
    update = command_update(command)
    if target:
        update = update.model_copy(
            update={
                "message": update.message.model_copy(
                    update={"reply_to_message": command_update("hello", user_id=target).message}
                )
            }
        )
    await feed(update)
    return runtime.game_cache.main(-1)


async def tap(app, game, user, action, round=1):
    feed, _, runtime = app
    await feed(callback(f"rp:{game.id}:{round}:{action}", user))
    await runtime.effects.drain()


async def point_count(sessions):
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(PointEvent))


async def test_one_board_hidden_moves_reveal_and_exact_once_award(game_app, sessions):
    _, transport, runtime = game_app
    with patch.object(runtime.sender, "send", wraps=runtime.sender.send) as outbound:
        game = await start(game_app)
        assert "&lt;Sinov&gt;" in transport.methods[-1].text
        await tap(game_app, game, 2, "a")
        await tap(game_app, game, 1, "r")
        board = [m for m in transport.methods if isinstance(m, EditMessageText)][-1]
        assert "tanladi" in board.text
        assert ": 🪨 Tosh" not in board.text and ": ✂️ Qaychi" not in board.text
        assert "winner" not in runtime.game_cache.main(-1).state
        await tap(game_app, game, 2, "s")
        assert runtime.game_cache.main(-1) is None
        board = [m for m in transport.methods if isinstance(m, EditMessageText)][-1]
        assert ": 🪨 Tosh" in board.text and ": ✂️ Qaychi" in board.text and "+2" in board.text
        assert board.message_id == 100 and board.reply_markup is None
        assert await point_count(sessions) == 1 and (await runtime.points.stats(-1, 1))[0] == 2
        await tap(game_app, game, 2, "s")
        assert await point_count(sessions) == 1
        assert all(call.kwargs["priority"] == Priority.GAME for call in outbound.call_args_list)
    assert sum(isinstance(m, SendMessage) for m in transport.methods) == 2  # welcome + lobby
    async with sessions() as session:
        finished = await session.get(GameSession, game.id)
        assert finished.status == "finished" and finished.phase_deadline_at is None
        assert texts.game_card_data(finished)["rows"] == [("<Sinov>", 2)]


async def test_concurrent_button_spam_one_choice_one_winner(game_app, sessions):
    feed, _, runtime = game_app
    game = await start(game_app)
    await tap(game_app, game, 2, "a")
    await asyncio.gather(*[feed(callback(f"rp:{game.id}:1:r", 1)) for _ in range(10)])
    await asyncio.gather(*[feed(callback(f"rp:{game.id}:1:s", 2)) for _ in range(10)])
    await runtime.effects.drain()
    assert await point_count(sessions) == 1
    assert (await runtime.points.stats(-1, 1))[0] == 2


async def test_draw_no_points_and_buttons_include_game_round(game_app, sessions):
    _, _, runtime = game_app
    game = await start(game_app, command="/toshqaychiqogoz")
    for button in game_keyboard(game).inline_keyboard[0]:
        assert button.callback_data == f"rp:{game.id}:1:a"
        assert len(button.callback_data.encode()) <= 64
    await tap(game_app, game, 2, "a")
    await tap(game_app, game, 2, "p")
    await tap(game_app, game, 1, "p")
    assert await point_count(sessions) == 0
    async with sessions() as session:
        final = await session.get(GameSession, game.id)
        assert final.status == "finished" and final.state["winner"] is None
        assert "Durang" in texts.rps_board(final) and texts.game_card_data(final) is None


async def test_target_permissions_stale_foreign_boards_and_locked_selection(game_app):
    feed, transport, runtime = game_app
    game = await start(game_app, target=2)
    for actor in (1, 3):
        await tap(game_app, game, actor, "a")
        assert runtime.game_cache.main(-1).state["phase"] == "lobby"
    await tap(game_app, game, 2, "a", round=2)
    assert runtime.game_cache.main(-1).state["phase"] == "lobby"
    update = callback(f"rp:{game.id}:1:a", 2)
    for message_id, chat_id in [(111, -1), (100, -5)]:
        query = update.callback_query.model_copy(
            update={
                "message": update.callback_query.message.model_copy(
                    update={
                        "message_id": message_id,
                        "chat": update.callback_query.message.chat.model_copy(
                            update={"id": chat_id}
                        ),
                    }
                )
            }
        )
        await feed(update.model_copy(update={"callback_query": query}))
    assert runtime.game_cache.main(-1).state["phase"] == "lobby"
    await tap(game_app, game, 2, "a")
    await tap(game_app, game, 3, "r")
    assert not runtime.game_cache.main(-1).state["choices"]
    await tap(game_app, game, 1, "r")
    await tap(game_app, game, 1, "p")
    assert runtime.game_cache.main(-1).state["choices"] == {"1": "r"}
    assert isinstance(transport.methods[-1], AnswerCallbackQuery)
    assert transport.methods[-1].text == texts.GAME_BUTTON_EXPIRED


@pytest.mark.parametrize("target", [1, 77, 123456789])
async def test_invalid_invited_players_do_not_create_sessions(game_app, target):
    feed, transport, runtime = game_app
    await start(game_app, target=target)
    assert runtime.game_cache.main(-1) is None
    assert transport.methods[-1].text == texts.DUEL_INVALID_TARGET
    await feed(command_update("/tqq", user_id=77))
    assert transport.methods[-1].text == texts.GAME_JOIN_FIRST


@pytest.mark.parametrize("accepted", [False, True])
async def test_deadline_rejects_late_choices_and_cancels_without_points(
    game_app, sessions, accepted
):
    _, _, runtime = game_app
    game = await start(game_app)
    if accepted:
        await tap(game_app, game, 2, "a")
        await tap(game_app, game, 1, "r")
    current = runtime.game_cache.main(-1)
    with patch("bot.services.rps.utc_now", return_value=current.phase_deadline_at):
        await tap(game_app, game, 2, "s" if accepted else "a")
    await runtime.game_hub.advance(current, current.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None and await point_count(sessions) == 0


async def test_timeout_never_waits_on_global_outbound_pause(game_app, sessions):
    _, _, runtime = game_app
    game = await start(game_app)

    async def blocked_sleep(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", blocked_sleep):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        await asyncio.wait_for(runtime.game_hub.advance(game, game.phase_deadline_at), 2)
        assert runtime.game_cache.main(-1) is None
        async with sessions() as session:
            assert (await session.get(GameSession, game.id)).status == "cancelled"
        assert runtime.effects.tasks


@pytest.mark.parametrize("stopper,stops", [(1, True), (42, True), (3, False)])
async def test_stop_only_starter_or_admin(game_app, sessions, stopper, stops):
    feed, _, runtime = game_app
    game = await start(game_app)
    await feed(command_update("/stop", user_id=stopper))
    assert (runtime.game_cache.main(-1) is None) is stops
    assert await point_count(sessions) == 0
    if stops:
        await tap(game_app, game, 2, "a")
        assert runtime.game_cache.main(-1) is None


@pytest.mark.parametrize("leaver,active", [(1, True), (2, True), (2, False)])
async def test_leave_or_opt_out_cancels_without_revealing_choice(
    game_app, sessions, leaver, active
):
    _, transport, runtime = game_app
    game = await start(game_app)
    await tap(game_app, game, 2, "a")
    await tap(game_app, game, 1, "r")
    await runtime.groups.membership(-1, tg_user(leaver), opted_in=False, active=active)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None and await point_count(sessions) == 0
    assert [m for m in transport.methods if isinstance(m, EditMessageText)][
        -1
    ].text == texts.RPS_LEFT


async def test_restart_migration_and_privacy_cancel_unfinished_games(game_app, sessions):
    _, _, runtime = game_app
    game = await start(game_app)
    await tap(game_app, game, 2, "a")
    await tap(game_app, game, 1, "r")
    await runtime.game_cache.load(sessions)
    await runtime.game_hub.recover(list(runtime.game_cache.records.values()))
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None and await point_count(sessions) == 0
    game = await start(game_app)
    await runtime.migrations.migrate(-1, -10055)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-10055) is None
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).chat_id == -10055
    # The same existing privacy service must find both participants in names/state.
    update = command_update("/tqq").message.model_copy(
        update={"chat": command_update("/tqq").message.chat.model_copy(update={"id": -10055})}
    )
    assert await runtime.rps_game.start(update) is None
    game = runtime.game_cache.main(-10055)
    assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.status == "cancelled" and row.state == {"erased": True}


async def test_main_game_slot_and_fast_callback_before_outbound_effects(game_app):
    feed, transport, runtime = game_app
    game = await start(game_app)
    await feed(command_update("/viktorina"))
    assert transport.methods[-1].text == texts.GAME_BUSY

    async def blocked_sleep(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", blocked_sleep):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        await asyncio.wait_for(feed(callback(f"rp:{game.id}:1:a", 2)), 2)
        assert transport.methods[-1].text == texts.RPS_ACCEPTED
        assert isinstance(transport.methods[-1], AnswerCallbackQuery)
        assert runtime.game_cache.main(-1).state["phase"] == "choosing"


async def test_malformed_callbacks_bots_and_unaccepted_target_opt_out(game_app, sessions):
    feed, _, runtime = game_app
    game = await start(game_app, target=2)
    before = runtime.game_cache.main(-1).state
    for data in [
        "rp:",
        "rp:no:1:a",
        "rp:-1:1:a",
        "rp:1:1:x",
        f"rp:{game.id}:0:a",
        f"rp:{game.id}:1:a:extra",
    ]:
        await feed(callback(data, 2))
    update = callback(f"rp:{game.id}:1:a", 2)
    await feed(
        update.model_copy(
            update={
                "callback_query": update.callback_query.model_copy(
                    update={"from_user": tg_user(2, True)}
                )
            }
        )
    )
    assert runtime.game_cache.main(-1).state == before
    await runtime.groups.membership(-1, tg_user(2), opted_in=False)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None and await point_count(sessions) == 0


async def test_invited_target_leaving_between_validation_and_creation_is_rechecked_under_lock(
    game_app,
):
    _, _, runtime = game_app
    original = runtime.games.start

    async def leave_then_create(*args, **kwargs):
        await runtime.groups.membership(-1, tg_user(2), opted_in=False)
        return await original(*args, **kwargs)

    with patch.object(runtime.games, "start", side_effect=leave_then_create):
        assert await start(game_app, target=2) is None
