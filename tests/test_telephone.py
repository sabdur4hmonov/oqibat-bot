import asyncio
import random
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import EditMessageCaption, GetChatMember, SendMessage, SendVoice
from aiogram.types import ChatMemberMember, Message
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import administrator, callback, tg_user
from test_guess_games import guess_app as guess_app
from test_private_games import dm_update, lobby

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games import telephone as engine
from bot.utils.time import utc_now


@pytest.fixture
async def media_app(guess_app):
    _, transport, runtime = guess_app
    original = transport.make_request
    sequence = 700

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        nonlocal sequence
        if isinstance(method, (SendVoice, EditMessageCaption)):
            transport.methods.append(method)
            sequence += 1
            return Message(
                message_id=getattr(method, "message_id", sequence),
                date=utc_now(),
                chat={
                    "id": method.chat_id,
                    "type": "private" if method.chat_id > 0 else "supergroup",
                },
                caption=method.caption,
            )
        return await original(bot, method, timeout)

    member = administrator(tg_user(runtime.game_hub.bot.id, True)).model_copy(
        update={"can_delete_messages": True}
    )
    with (
        patch.object(transport, "make_request", side_effect=request),
        patch.object(runtime.game_hub.bot, "get_chat_member", new=AsyncMock(return_value=member)),
    ):
        yield guess_app


def voice(user, duration=30, message_id=500, *, file_id=None, caption=None):
    update = dm_update("", user, message_id)
    payload = update.model_dump()
    payload["message"].update(
        text=None,
        entities=[],
        voice={
            "file_id": file_id or f"voice_{user}",
            "file_unique_id": f"unique_{user}",
            "duration": duration,
        },
        caption=caption,
    )
    return update.__class__.model_validate(payload)


async def telephone_game(app):
    runtime = app[2]
    game = await lobby(app, "telephone", (1, 2, 3, 42))
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


async def complete(app):
    feed, _, runtime = app
    game = await telephone_game(app)
    game_id, order = game.id, list(game.state["order"])
    for index, user in enumerate(order):
        if index == len(order) - 1:
            await feed(dm_update("<Oxirgi> & jumla", int(user), 600 + index))
        else:
            await feed(voice(int(user), message_id=600 + index))
        await runtime.effects.drain()
        game = runtime.game_cache.get(game_id)
    return game_id, order


def test_pure_telephone_order_limits_and_rewards():
    for count in range(4, 11):
        players = list(map(str, range(count)))
        assert sorted(engine.player_order(players, random.Random(7))) == sorted(players)
    for players in (["1"] * 4, ["1", "2", "3"], list(map(str, range(11)))):
        with pytest.raises(ValueError):
            engine.player_order(players)
    assert engine.valid_voice(0) and engine.valid_voice(30)
    assert not any(engine.valid_voice(value) for value in (-1, 31, True, 1.5))
    assert engine.rewards({"1": {"user_id": 1}, "2": {"user_id": 2, "hidden": True}}) == {"1": 3}


async def test_telephone_full_chain_only_previous_voice_and_points_once(media_app, sessions):
    _, transport, runtime = media_app
    game_id, order = await complete(media_app)
    assert runtime.game_cache.get(game_id) is None and not runtime.private_contexts.users
    async with sessions() as session:
        game = await session.get(GameSession, game_id)
        assert game.status == "finished" and sum(game.state["scores"].values()) == 12
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 12
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 4
    private_voices = [
        method
        for method in transport.methods
        if isinstance(method, SendVoice) and method.chat_id > 0
    ]
    assert [method.chat_id for method in private_voices] == list(map(int, order[1:]))
    assert [method.voice for method in private_voices] == [f"voice_{user}" for user in order[:-1]]
    phrase = game.state["phrase"]
    assert not any(
        isinstance(method, SendMessage)
        and method.chat_id in set(map(int, order[1:]))
        and phrase in method.text
        for method in transport.methods
    )
    group = [
        method
        for method in transport.methods
        if isinstance(method, (SendMessage, SendVoice)) and method.chat_id == -1
    ]
    original_index = next(
        index
        for index, method in enumerate(group)
        if isinstance(method, SendMessage)
        and method.text == texts.TELEPHONE_ORIGINAL.format(phrase=texts.escape(phrase))
    )
    reveal = group[original_index:]
    assert isinstance(reveal[1], SendMessage) and "&lt;Oxirgi&gt; &amp;" in reveal[1].text
    assert [method.voice for method in reveal if isinstance(method, SendVoice)] == [
        f"voice_{user}" for user in order[:-1]
    ]
    assert all(
        method.reply_markup.inline_keyboard[-1][0].callback_data.startswith(f"ph:{game_id}:")
        for method in reveal[1:]
    )
    assert (
        await runtime.telephone.private_input(
            runtime.game_cache.get(game_id) or game, voice(int(order[0])).message
        )
        == texts.PRIVATE_GAME_INPUT_WAIT
    )


async def test_telephone_input_guards_foreign_bot_stale_and_duplicate(media_app):
    feed, transport, runtime = media_app
    game = await telephone_game(media_app)
    user = int(game.state["order"][0])
    other = int(game.state["order"][1])
    await feed(voice(other))
    assert transport.methods[-1].text == texts.PRIVATE_GAME_INPUT_WAIT
    await feed(voice(user, 31))
    assert transport.methods[-1].text == texts.PRIVATE_GAME_INVALID
    await feed(voice(user, caption="@bad"))
    assert transport.methods[-1].text == texts.PRIVATE_GAME_INVALID
    old = voice(user).message.model_copy(update={"date": utc_now() - timedelta(days=1)})
    assert await runtime.telephone.private_input(game, old) == texts.PRIVATE_GAME_INPUT_WAIT
    bot_message = voice(user).message.model_copy(update={"from_user": tg_user(user, True)})
    assert await runtime.telephone.private_input(game, bot_message) == texts.PRIVATE_GAME_INVALID
    await asyncio.gather(feed(voice(user)), feed(voice(user, message_id=501)))
    await runtime.effects.drain()
    current = runtime.game_cache.get(game.id)
    assert current.state["turn"] == 1 and len(current.state["items"]) == 1
    assert (
        await runtime.telephone.callback(callback(f"pg:{game.id}:0:v:{user}", other).callback_query)
        == texts.PRIVATE_GAME_CLOSED
    )


async def test_telephone_middle_timeout_passes_last_voice_and_last_timeout_finishes(
    media_app, sessions
):
    feed, transport, runtime = media_app
    game = await telephone_game(media_app)
    order = game.state["order"]
    await feed(voice(int(order[0])))
    await runtime.effects.drain()
    middle = runtime.game_cache.get(game.id)
    await runtime.game_hub.advance(middle, middle.phase_deadline_at)
    await runtime.effects.drain()
    current = runtime.game_cache.get(game.id)
    assert current.state["turn"] == 2
    sent = [
        method
        for method in transport.methods
        if isinstance(method, SendVoice) and method.chat_id == int(order[2])
    ]
    assert sent[-1].voice == f"voice_{order[0]}"
    await feed(voice(int(order[2])))
    await runtime.effects.drain()
    last = runtime.game_cache.get(game.id)
    await runtime.game_hub.advance(last, last.phase_deadline_at)
    await runtime.effects.drain()
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.status == "finished"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 6
    assert any(
        isinstance(method, SendMessage) and method.text == texts.TELEPHONE_MISSING
        for method in transport.methods
    )


async def test_telephone_all_timeouts_cancel_no_points(media_app, sessions):
    runtime = media_app[2]
    game = await telephone_game(media_app)
    while game:
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await runtime.effects.drain()
        game = runtime.game_cache.get(game.id)
    assert not runtime.private_contexts.users
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_media_requires_delete_permission_before_lobby(guess_app):
    _, _, runtime = guess_app
    assert (
        await runtime.private_games.start(command_update("/telefon").message, "telephone")
        == texts.PRIVATE_GAME_NEED_DELETE
    )
    assert not runtime.game_cache.for_chat(-1)


@pytest.mark.parametrize("action", ["stop", "restart", "migration", "erasure", "leave"])
async def test_telephone_lifecycle_and_context_consent(media_app, sessions, action):
    feed, transport, runtime = media_app
    game = await telephone_game(media_app)
    first = int(game.state["order"][0])
    await feed(voice(first))
    await runtime.effects.drain()
    board = next(
        method
        for method in transport.methods
        if isinstance(method, SendMessage)
        and method.chat_id == -1
        and "Ovozli buzilgan telefon" in method.text
    )
    assert "rozilik" in board.text and "ovozlar" in board.text
    await runtime.private_games.start(command_update("/yashirin", 900).message)
    secret = runtime.game_cache.background(-1)
    assert (
        await runtime.private_games.join(secret.id, tg_user(first), "secret")
        == texts.PRIVATE_GAME_BUSY
    )
    if action == "stop":
        assert await runtime.game_hub.stop(-1, 1) is None
    elif action == "restart":
        await runtime.telephone.recover(runtime.game_cache.get(game.id))
    elif action == "migration":
        await runtime.migrations.migrate(-1, -1001234)
    elif action == "erasure":
        assert await runtime.owner_tools.erase(first, runtime.owner_tools.confirm(first))
    else:
        await runtime.groups.membership(-1, tg_user(first), opted_in=False)
    await runtime.effects.drain()
    assert not runtime.private_contexts.users
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.status == "cancelled"
        if action == "erasure":
            assert row.state == {"erased": True}
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_telephone_hide_after_finish_reverses_author_once_and_caption_fallback(
    media_app, sessions
):
    _, transport, runtime = media_app
    game_id, order = await complete(media_app)
    async with sessions() as session:
        row = await session.get(GameSession, game_id)
        item = row.state["items"][order[0]]
    query = callback(f"ph:{game_id}:{order[0]}", 1).callback_query
    query = query.model_copy(
        update={"message": query.message.model_copy(update={"message_id": item["message_id"]})}
    )
    assert await runtime.private_games.hide(query) == texts.PRIVATE_GAME_HIDE_DENIED
    admin = query.model_copy(update={"from_user": tg_user(42)})
    member = ChatMemberMember(user=tg_user(runtime.game_hub.bot.id, True))
    with patch.object(runtime.game_hub.bot, "get_chat_member", new=AsyncMock(return_value=member)):
        assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_HIDE_MEDIA
    assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_CLOSED
    await runtime.effects.drain()
    assert any(
        isinstance(method, EditMessageCaption) and method.caption == texts.PRIVATE_GAME_HIDDEN
        for method in transport.methods
    )
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 9


async def test_forbidden_turn_dm_skips_player_without_exposing_phrase_to_others(media_app):
    _, transport, runtime = media_app
    original = transport.make_request
    failed = False

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        nonlocal failed
        if (
            not failed
            and isinstance(method, SendMessage)
            and method.chat_id > 0
            and texts.TELEPHONE_FIRST.split("{")[0] in method.text
        ):
            failed = True
            raise TelegramForbiddenError(method=method, message="blocked")
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        game = await telephone_game(media_app)
    assert failed and game.state["turn"] == 1
    assert not game.state["last_voice"]


async def test_permission_429_pauses_global_sender_and_fails_closed(media_app):
    runtime = media_app[2]
    method = GetChatMember(chat_id=-1, user_id=runtime.game_hub.bot.id)
    error = TelegramRetryAfter(method=method, message="wait", retry_after=7)
    with patch.object(runtime.game_hub.bot, "get_chat_member", new=AsyncMock(side_effect=error)):
        assert not await runtime.private_games.can_delete(-1)
    assert runtime.sender.limiter.global_pause >= runtime.sender.clock.now() + 7


async def test_finished_media_hide_does_not_reuse_old_message_id_after_migration(media_app):
    _, transport, runtime = media_app
    game_id, order = await complete(media_app)
    async with runtime.sessions() as session:
        row = await session.get(GameSession, game_id)
        message_id = row.state["items"][order[0]]["message_id"]
    await runtime.migrations.migrate(-1, -1001234)
    await runtime.effects.drain()
    admin = callback(f"ph:{game_id}:{order[0]}", 42).callback_query
    admin = admin.model_copy(
        update={
            "message": admin.message.model_copy(
                update={
                    "message_id": message_id,
                    "chat": admin.message.chat.model_copy(update={"id": -1001234}),
                }
            )
        }
    )
    before = len(transport.methods)
    assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_CLOSED
    assert not any(
        method.__class__.__name__ in {"DeleteMessage", "EditMessageCaption"}
        for method in transport.methods[before:]
    )


async def test_hidden_voice_before_reveal_finishes_receives_no_points(media_app, sessions):
    feed, transport, runtime = media_app
    game = await telephone_game(media_app)
    order = game.state["order"]
    for user in order[:-1]:
        await feed(voice(int(user)))
        await runtime.effects.drain()
    started, release, hidden = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if (
            isinstance(method, SendVoice)
            and method.chat_id == -1
            and method.voice == f"voice_{order[1]}"
        ):
            started.set()
            await release.wait()
        return await original(bot, method, timeout)

    def changed(row, old=None):
        if row.id == game.id and row.state.get("items", {}).get(order[0], {}).get("hidden"):
            hidden.set()

    runtime.game_cache.listeners.append(changed)
    with patch.object(transport, "make_request", side_effect=request):
        await feed(dm_update("Oxirgi matn", int(order[-1])))
        await asyncio.wait_for(started.wait(), 2)
        current = runtime.game_cache.get(game.id)
        item = current.state["items"][order[0]]
        admin = callback(f"ph:{game.id}:{order[0]}", 42).callback_query
        admin = admin.model_copy(
            update={"message": admin.message.model_copy(update={"message_id": item["message_id"]})}
        )
        hiding = asyncio.create_task(runtime.private_games.hide(admin))
        try:
            await asyncio.wait_for(hidden.wait(), 2)
        finally:
            release.set()
        assert await hiding == texts.PRIVATE_GAME_HIDE_DONE
        await runtime.effects.drain()
    runtime.game_cache.listeners.remove(changed)
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 9
        assert (await session.get(GameSession, game.id)).state["items"][order[0]][
            "author_points"
        ] == 0
