import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage
from sqlalchemy import func, select
from test_easy_games import game_app as game_app
from test_group_flows import administrator, callback, tg_user
from test_private_games import dm_update, lobby

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games.private_input import guess_rewards
from bot.utils.time import utc_now


@pytest.fixture
async def guess_app(game_app):
    _, transport, _ = game_app
    original = transport.make_request
    sequence = 300

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        nonlocal sequence
        if isinstance(method, DeleteMessage):
            transport.methods.append(method)
            return True
        result = await original(bot, method, timeout)
        if isinstance(method, SendMessage):
            sequence += 1
            result = result.model_copy(update={"message_id": sequence})
        return result

    with patch.object(transport, "make_request", side_effect=request):
        yield game_app


def vote_query(game, user, target, *, round_number=None, message_id=None):
    query = callback(
        f"pg:{game.id}:{game.state['round'] if round_number is None else round_number}:v:{target}",
        user,
    ).callback_query
    item = game.state["items"][game.state["item"]]
    return query.model_copy(
        update={
            "message": query.message.model_copy(
                update={"message_id": item["message_id"] if message_id is None else message_id}
            )
        }
    )


async def collecting(app, kind="kim", users=(1, 2, 3, 42)):
    runtime = app[2]
    game = await lobby(app, kind, users)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


async def answers(app):
    feed, _, runtime = app
    game = await collecting(app)
    for user in (1, 2, 3, 42):
        await feed(dm_update(f"<Javob> & {user}", user, 400 + user))
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


def test_pure_guess_scoring_author_bonus_and_hidden_item():
    assert guess_rewards("1", {"2": "1", "3": "1", "1": "1"}) == {"2": 3, "3": 3}
    assert guess_rewards("1", {"2": "3"}) == {"1": 3}
    assert guess_rewards("1", {}, True) == {}
    assert guess_rewards("1", {"2": "1"}, True) == {"2": 3}


async def test_kim_complete_game_correct_and_unguessed_author_points_once(guess_app, sessions):
    _, transport, runtime = guess_app
    game = await answers(guess_app)
    assert game.state["phase"] == "guess"
    expected = 0
    old_query = None
    while game:
        item = game.state["items"][game.state["item"]]
        author = str(item["user_id"])
        if game.state["round"] % 2:
            voters = [int(user) for user in game.state["players"] if user != author][:2]
            results = await asyncio.gather(
                *(runtime.guess_games.callback(vote_query(game, user, author)) for user in voters)
            )
            assert results == [texts.PRIVATE_GUESS_SAVED] * 2
            assert (
                await runtime.guess_games.callback(vote_query(game, voters[0], author))
                == texts.PRIVATE_GAME_CLOSED
            )
            expected += 6
        else:
            expected += 3
        assert (
            await runtime.guess_games.callback(vote_query(game, int(author), author))
            == texts.PRIVATE_GUESS_DENIED
        )
        if old_query:
            assert await runtime.guess_games.callback(old_query) == texts.PRIVATE_GAME_CLOSED
        old_query = vote_query(
            game, next(int(user) for user in game.state["players"] if user != author), author
        )
        current = runtime.game_cache.get(game.id)
        await asyncio.gather(
            runtime.game_hub.advance(current, current.phase_deadline_at),
            runtime.game_hub.advance(current, current.phase_deadline_at),
        )
        await runtime.effects.drain()
        game = runtime.game_cache.get(current.id)
    async with sessions() as session:
        assert (await session.get(GameSession, current.id)).status == "finished"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == expected == 18
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 6
    assert not runtime.private_contexts.users
    anonymous = [
        method
        for method in transport.methods
        if isinstance(method, SendMessage) and method.chat_id == -1 and "Kim yozgan?" in method.text
    ]
    assert (
        len(anonymous) == 4
        and len({method.reply_markup.inline_keyboard[-1][0].callback_data for method in anonymous})
        == 4
    )
    assert all(
        "&lt;Javob&gt; &amp;" in method.text and "Muallif:" not in method.text
        for method in anonymous
    )


async def test_kim_callback_context_consent_and_validation(guess_app):
    feed, transport, runtime = guess_app
    game = await answers(guess_app)
    item = game.state["items"][game.state["item"]]
    author = str(item["user_id"])
    voter = next(int(user) for user in game.state["players"] if user != author)
    query = vote_query(game, voter, author)
    invalid = [
        query.model_copy(update={"from_user": tg_user(voter, True)}),
        vote_query(game, 999, author),
        vote_query(game, voter, author, round_number=0),
        vote_query(game, voter, author, message_id=99),
        query.model_copy(
            update={
                "message": query.message.model_copy(
                    update={"chat": query.message.chat.model_copy(update={"id": -999})}
                )
            }
        ),
    ]
    for candidate in invalid:
        assert await runtime.guess_games.callback(candidate) != texts.PRIVATE_GUESS_SAVED
    assert not runtime.game_cache.get(game.id).state["votes"]
    lobby_post = next(
        method
        for method in transport.methods
        if isinstance(method, SendMessage) and "Kim aytdi?" in method.text and method.chat_id == -1
    )
    assert "rozilik" in lobby_post.text and "ismingiz" in lobby_post.text
    await feed(dm_update("Boshqa javob", voter))
    assert transport.methods[-1].text == texts.PRIVATE_GAME_INPUT_WAIT


@pytest.mark.parametrize("text", ["https://example.uz", "@odam", "a" * 301, "   "])
async def test_kim_private_input_rejections_and_duplicate(guess_app, text):
    feed, transport, runtime = guess_app
    game = await collecting(guess_app)
    await feed(dm_update(text))
    assert transport.methods[-1].text == texts.PRIVATE_GAME_INVALID
    assert not runtime.game_cache.get(game.id).state["items"]
    await feed(dm_update("Yaxshi <javob>", message_id=500))
    await feed(dm_update("Ikkinchi javob", message_id=501))
    assert runtime.game_cache.get(game.id).state["items"]["1"]["text"] == "Yaxshi <javob>"
    assert len(runtime.game_cache.get(game.id).state["items"]) == 1


async def test_kim_hide_before_award_and_after_finish_compensates_once(guess_app, sessions):
    _, transport, runtime = guess_app
    game = await answers(guess_app)
    first = game.state["item"]
    item = game.state["items"][first]
    query = callback(f"ph:{game.id}:{first}", 1).callback_query
    query = query.model_copy(
        update={"message": query.message.model_copy(update={"message_id": item["message_id"]})}
    )
    assert await runtime.private_games.hide(query) == texts.PRIVATE_GAME_HIDE_DENIED
    admin = query.model_copy(update={"from_user": tg_user(42)})
    assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_HIDE_DONE
    await runtime.effects.drain()
    while current := runtime.game_cache.get(game.id):
        await runtime.game_hub.advance(current, current.phase_deadline_at)
        await runtime.effects.drain()
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.state["items"][first]["author_points"] == 0
        other_id, other = next(
            (key, item) for key, item in row.state["items"].items() if key != first
        )
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 9
    late = admin.model_copy(
        update={
            "data": f"ph:{game.id}:{other_id}",
            "message": admin.message.model_copy(update={"message_id": other["message_id"]}),
        }
    )
    assert await runtime.private_games.hide(late) == texts.PRIVATE_GAME_HIDE_DONE
    assert await runtime.private_games.hide(late) == texts.PRIVATE_GAME_CLOSED
    await runtime.effects.drain()
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 6
    edits = [
        method
        for method in transport.methods
        if isinstance(method, EditMessageText) and method.message_id == item["message_id"]
    ]
    assert edits[-1].text == texts.PRIVATE_GAME_HIDDEN


async def test_kim_deadlines_empty_collection_and_minimum_lobby(guess_app):
    runtime = guess_app[2]
    game = await collecting(guess_app)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(game.id) is None
    second = await lobby(guess_app, "kim", (1, 2, 3))
    await runtime.game_hub.advance(second, second.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(second.id) is None


@pytest.mark.parametrize("action", ["stop", "restart", "migration", "erasure", "leave"])
async def test_kim_lifecycle_no_late_answer_reveal_and_context_released(
    guess_app, sessions, action
):
    feed, _, runtime = guess_app
    game = await collecting(guess_app)
    await feed(dm_update("Shaxsiy javob"))
    if action == "stop":
        assert await runtime.game_hub.stop(-1, 1) is None
    elif action == "restart":
        await runtime.guess_games.recover(game)
    elif action == "migration":
        await runtime.migrations.migrate(-1, -1001234)
    elif action == "erasure":
        assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    else:
        await runtime.groups.membership(-1, tg_user(2), opted_in=False)
    await runtime.effects.drain()
    assert not runtime.private_contexts.users
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.status == "cancelled"
        if action == "erasure":
            assert row.state == {"erased": True}
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_early_answer_during_other_players_prompts_is_kept(guess_app):
    feed, transport, runtime = guess_app
    game = await lobby(guess_app, "kim", (1, 2, 3, 42))
    original = runtime.private_games.dm
    started, release = asyncio.Event(), asyncio.Event()

    async def delayed(snapshot, user, text):
        if user == "2":
            started.set()
            await release.wait()
        return await original(snapshot, user, text)

    with patch.object(runtime.private_games, "dm", side_effect=delayed):
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await asyncio.wait_for(started.wait(), 2)
        try:
            await feed(dm_update("Erta javob", 1))
            assert runtime.game_cache.get(game.id).state["items"]["1"]["text"] == "Erta javob"
        finally:
            release.set()
        await runtime.effects.drain()
    current = runtime.game_cache.get(game.id)
    assert current.state["phase"] == "collect"
    assert current.phase_deadline_at > utc_now() + timedelta(minutes=4)


async def test_admin_hide_with_delete_permission_uses_delete(guess_app):
    _, transport, runtime = guess_app
    game = await answers(guess_app)
    item_id = game.state["item"]
    message_id = game.state["items"][item_id]["message_id"]
    admin = callback(f"ph:{game.id}:{item_id}", 42).callback_query
    admin = admin.model_copy(
        update={"message": admin.message.model_copy(update={"message_id": message_id})}
    )
    member = administrator(tg_user(runtime.game_hub.bot.id, True)).model_copy(
        update={"can_delete_messages": True}
    )
    from unittest.mock import AsyncMock

    with patch.object(runtime.game_hub.bot, "get_chat_member", new=AsyncMock(return_value=member)):
        assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_HIDE_DONE
    await runtime.effects.drain()
    assert any(
        isinstance(method, DeleteMessage) and method.message_id == message_id
        for method in transport.methods
    )


async def test_slow_author_reveal_cannot_overwrite_admin_hide(guess_app):
    _, transport, runtime = guess_app
    game = await answers(guess_app)
    item_id = game.state["item"]
    message_id = game.state["items"][item_id]["message_id"]
    started, release = asyncio.Event(), asyncio.Event()
    original = transport.make_request
    applied = []

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, EditMessageText) and method.message_id == message_id:
            if "Muallif:" in method.text:
                started.set()
                await release.wait()
            applied.append(method.text)
        return await original(bot, method, timeout)

    admin = callback(f"ph:{game.id}:{item_id}", 42).callback_query
    admin = admin.model_copy(
        update={"message": admin.message.model_copy(update={"message_id": message_id})}
    )
    hidden = asyncio.Event()

    def changed(row, old=None):
        if row.id == game.id and row.state.get("items", {}).get(item_id, {}).get("hidden"):
            hidden.set()

    runtime.game_cache.listeners.append(changed)
    with patch.object(transport, "make_request", side_effect=request):
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await asyncio.wait_for(started.wait(), 2)
        hiding = asyncio.create_task(runtime.private_games.hide(admin))
        try:
            await asyncio.wait_for(hidden.wait(), 2)
        finally:
            release.set()
        assert await hiding == texts.PRIVATE_GAME_HIDE_DONE
        await runtime.effects.drain()
    runtime.game_cache.listeners.remove(changed)
    assert applied[-1] == texts.PRIVATE_GAME_HIDDEN
