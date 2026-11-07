import asyncio
from datetime import datetime
from unittest.mock import patch

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import DeleteMessage, EditMessageText, GetChatMember, SendMessage
from aiogram.types import Update
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import administrator, callback, tg_user

from bot import texts
from bot.db.models import Chat, GameSession, PointEvent
from bot.games.mafia.roles import COMMISSIONER, DOCTOR, MAFIA, TOWN
from bot.keyboards import mafia as keyboards
from bot.utils.time import utc_now


def start_link(session_id, user):
    return Update.model_validate(
        {
            "update_id": 1000 + user,
            "message": {
                "message_id": 50,
                "date": int(utc_now().timestamp()),
                "chat": {"id": user, "type": "private"},
                "from": tg_user(user).model_dump(),
                "text": f"/start mafia_{session_id}",
                "entities": [{"type": "bot_command", "offset": 0, "length": 6}],
            },
        }
    )


def action(game, user, operation, target, *, round_number=None, private=None):
    if private is None:
        private = operation != "v"
    round_value = game.state["round"] if round_number is None else round_number
    update = callback(
        f"mf:{game.id}:{round_value}:{operation}:{target}",
        int(user),
    )
    if private:
        query = update.callback_query
        message = query.message.model_copy(
            update={
                "chat": query.message.chat.model_copy(update={"id": int(user), "type": "private"})
            }
        )
        update = update.model_copy(
            update={"callback_query": query.model_copy(update={"message": message})}
        )
    return update


async def lobby(app, count=5):
    feed, transport, runtime = app
    for user in range(1, count + 1):
        await runtime.groups.membership(-1, tg_user(user), opted_in=True)
    await feed(command_update("/mafia"))
    game = runtime.game_cache.main(-1)
    for user in range(1, count + 1):
        await feed(start_link(game.id, user))
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


async def advance(app):
    feed, transport, runtime = app
    game = runtime.game_cache.main(-1)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    return runtime.game_cache.main(-1)


def who(game, role):
    return next(user for user, value in game.state["roles"].items() if value == role)


async def test_deep_link_only_lobby_edits_optin_and_global_join_race(game_app, sessions):
    feed, transport, runtime = game_app
    await feed(command_update("/mafia"))
    first = runtime.game_cache.main(-1)
    board = next(m for m in transport.methods if isinstance(m, SendMessage) and "Mafia" in m.text)
    assert board.reply_markup.inline_keyboard[0][0].url.endswith(f"start=mafia_{first.id}")
    await feed(start_link(first.id, 77))
    assert transport.methods[-1].text == texts.MAFIA_OPT_IN
    async with sessions.begin() as session:
        session.add(Chat(id=-2, title="Other", bot_is_admin=True))
    await runtime.groups.membership(-2, tg_user(1), opted_in=True)
    await runtime.groups.membership(-2, tg_user(2), opted_in=True)
    second_message = command_update("/mafia").message
    second_message = second_message.model_copy(
        update={"chat": second_message.chat.model_copy(update={"id": -2})}
    )
    await runtime.mafia_game.start(second_message)
    second = runtime.game_cache.main(-2)
    results = await asyncio.gather(
        runtime.mafia_game.join(first.id, tg_user(2)),
        runtime.mafia_game.join(second.id, tg_user(2)),
    )
    assert results.count(texts.MAFIA_JOINED) == 1
    assert results.count(texts.MAFIA_ALREADY_PLAYING) == 1
    await runtime.effects.drain()
    assert (
        len(
            [
                m
                for m in transport.methods
                if isinstance(m, SendMessage) and m.chat_id == -1 and "Mafia" in m.text
            ]
        )
        == 1
    )


async def test_full_five_player_town_win_commissioner_and_stale_buttons(game_app, sessions):
    feed, transport, runtime = game_app
    await lobby(game_app)
    game = await advance(game_app)
    assert game.state["phase"] == "night"
    mafia, cop = who(game, MAFIA), who(game, COMMISSIONER)
    await feed(action(game, cop, "c", mafia))
    assert transport.methods[-1].text == texts.MAFIA_IS_MAFIA
    await feed(action(game, cop, "c", mafia))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    await feed(start_link(game.id, 42))
    assert transport.methods[-1].text == texts.MAFIA_LOBBY_CLOSED
    game = await advance(game_app)  # no mafia vote = no kill
    assert len(game.state["alive"]) == 5
    await feed(action(game, mafia, "m", cop))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    game = await advance(game_app)
    for user in list(game.state["alive"]):
        await feed(action(game, user, "v", mafia))
    await runtime.effects.drain()
    game_id = game.id
    await advance(game_app)
    assert runtime.game_cache.main(-1) is None
    async with sessions() as session:
        saved = await session.get(GameSession, game_id)
        assert saved.state["winner"] == "town"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 52
    await feed(action(game, mafia, "v", cop))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    assert not runtime.mafia_game.members


async def test_full_five_player_mafia_win_dead_actions_and_round_context(game_app, sessions):
    feed, transport, runtime = game_app
    await lobby(game_app)
    game = await advance(game_app)
    mafia, doctor = who(game, MAFIA), who(game, DOCTOR)
    towns = [user for user, role in game.state["roles"].items() if role == TOWN]
    await feed(action(game, mafia, "m", towns[0]))
    await feed(action(game, doctor, "d", doctor))
    await runtime.effects.drain()
    game = await advance(game_app)
    assert towns[0] not in game.state["alive"]
    game = await advance(game_app)
    await feed(action(game, towns[0], "v", mafia))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    for user in game.state["alive"]:
        await feed(action(game, user, "v", towns[1]))
    await runtime.effects.drain()
    game = await advance(game_app)
    assert game.state["round"] == 2
    await feed(action(game, mafia, "m", doctor, round_number=1))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    await feed(action(game, doctor, "d", doctor))
    assert transport.methods[-1].text == texts.MAFIA_STALE
    await feed(action(game, mafia, "m", doctor))
    await runtime.effects.drain()
    game_id = game.id
    await advance(game_app)
    async with sessions() as session:
        assert (await session.get(GameSession, game_id)).state["winner"] == "mafia"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 16


@pytest.mark.parametrize("count,remaining", [(6, 5), (5, 4)])
async def test_forbidden_role_dm_prunes_before_assignment_and_rebalances_or_cancels(
    game_app, sessions, count, remaining
):
    feed, transport, runtime = game_app
    game = await lobby(game_app, count)
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, SendMessage) and method.chat_id == count:
            raise TelegramForbiddenError(method, "blocked")
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        await advance(game_app)
    async with sessions() as session:
        saved = await session.get(GameSession, game.id)
        assert len(saved.state["players"]) == remaining
        assert str(count) not in saved.state.get("roles", {})
        if remaining >= 5:
            assert saved.state["phase"] == "night"
            assert sorted(saved.state["roles"].values()) == sorted(
                [MAFIA, DOCTOR, COMMISSIONER, TOWN, TOWN]
            )
        else:
            assert saved.status == "cancelled" and "roles" not in saved.state
    assert any(
        isinstance(m, EditMessageText) and m.chat_id == -1 and "ro‘yxatdan olindi" in m.text
        for m in transport.methods
    )


async def test_mafia_peers_private_live_tally_and_callback_payloads(game_app):
    feed, transport, runtime = game_app
    await lobby(game_app, 7)
    game = await advance(game_app)
    mafias = [user for user, role in game.state["roles"].items() if role == MAFIA]
    target = who(game, TOWN)
    before = len(transport.methods)
    await feed(action(game, mafias[0], "m", target))
    await runtime.effects.drain()
    updates = [m for m in transport.methods[before:] if isinstance(m, EditMessageText)]
    assert {m.chat_id for m in updates} == {int(user) for user in mafias}
    assert all("Mafia jamoasi" in m.text and ": 1" in m.text for m in updates)
    for user in game.state["players"]:
        markup = keyboards.actions(game, int(user))
        if markup:
            for row in markup.inline_keyboard:
                for button in row:
                    assert button.callback_data.startswith(f"mf:{game.id}:1:")
                    assert len(button.callback_data.encode()) <= 64
    await feed(action(game, mafias[0], "m", target, private=False))
    assert transport.methods[-1].text == texts.MAFIA_STALE


async def test_stop_and_restart_cancel_and_notify_private_players_without_points(
    game_app, sessions
):
    feed, transport, runtime = game_app
    game = await lobby(game_app)
    await advance(game_app)
    before = len(transport.methods)
    await feed(command_update("/stop"))
    messages = [
        m
        for m in transport.methods[before:]
        if isinstance(m, (SendMessage, EditMessageText)) and m.chat_id > 0
    ]
    assert {m.chat_id for m in messages} == {1, 2, 3, 4, 5}
    await lobby(game_app)
    game = await advance(game_app)
    await runtime.mafia_game.recover(game)
    await runtime.effects.drain()
    assert runtime.game_cache.main(-1) is None
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_dead_message_setting_defaults_off_checks_delete_right_and_live_toggle(game_app):
    feed, transport, runtime = game_app
    await lobby(game_app)
    game = await advance(game_app)
    victim, mafia = who(game, TOWN), who(game, MAFIA)
    await feed(action(game, mafia, "m", victim))
    await runtime.effects.drain()
    await advance(game_app)
    original = transport.make_request
    can_delete = False

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, GetChatMember) and method.user_id == bot.id:
            transport.methods.append(method)
            return administrator(tg_user(bot.id, True)).model_copy(
                update={"can_delete_messages": can_delete}
            )
        if isinstance(method, DeleteMessage):
            transport.methods.append(method)
            return True
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        await feed(command_update("hello", 901, int(victim)))
        await runtime.effects.drain()
        assert not any(isinstance(m, DeleteMessage) for m in transport.methods)
        await runtime.groups.change_setting(-1, "mafia_delete_dead_messages", True)
        await feed(command_update("hello", 902, int(victim)))
        await runtime.effects.drain()
        assert not any(isinstance(m, DeleteMessage) for m in transport.methods)
        can_delete = True
        with patch(
            "sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=AssertionError("SQL")
        ):
            await feed(command_update("hello", 903, int(victim)))
            await runtime.effects.drain()
        assert [m.message_id for m in transport.methods if isinstance(m, DeleteMessage)] == [903]


async def test_deadlines_do_not_wait_for_global_send_pause(game_app, sessions):
    feed, transport, runtime = game_app
    await lobby(game_app)
    game = await advance(game_app)

    async def sleep(_):
        await asyncio.Event().wait()

    with patch.object(runtime.sender.clock, "sleep", new=sleep):
        runtime.sender.limiter.pause(None, runtime.sender.clock.now() + 3600)
        await asyncio.wait_for(runtime.game_hub.advance(game, game.phase_deadline_at), 2)
        async with sessions() as session:
            assert (await session.get(GameSession, game.id)).state["phase"] == "discussion"


async def test_migration_rekeys_registry_and_recreates_board_for_active_mafia(game_app):
    feed, transport, runtime = game_app
    await lobby(game_app)
    game = await advance(game_app)
    await runtime.migrations.migrate(-1, -1001234567890)
    assert runtime.mafia_game.members[1] == game.id
    await runtime.mafia_game.group_board(game.id)
    game = runtime.game_cache.get(game.id)
    assert game.chat_id == -1001234567890 and game.state["board_id"] is not None


async def test_preparation_reaching_hour_cap_ends_draw_without_assigning_roles(game_app, sessions):
    feed, transport, runtime = game_app
    game = await lobby(game_app)

    def preparing(row):
        row.state["phase"] = "preparing"
        row.status = "running"
        row.phase_deadline_at = datetime.fromisoformat(row.state["hard_deadline"])

    game = await runtime.games.transition(-1, game.id, preparing)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    async with sessions() as session:
        saved = await session.get(GameSession, game.id)
        assert saved.status == "finished" and saved.state["winner"] == "draw"
        assert not saved.state["roles"]
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
