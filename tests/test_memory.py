import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import DeleteMessage, EditMessageCaption, SendPhoto
from aiogram.types import ChatMemberMember, MessageOriginHiddenUser
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user
from test_guess_games import collecting, vote_query
from test_guess_games import guess_app as guess_app
from test_private_games import dm_update, lobby
from test_telephone import media_app as media_app
from test_telephone import voice

from bot import texts
from bot.db.models import GameSession, PointEvent
from bot.games.private_input import guess_rewards
from bot.utils.time import utc_now


def photo(user=1, caption=None, message_id=1000, file_id=None):
    update = dm_update("", user, message_id)
    data = update.model_dump()
    data["message"].update(
        text=None,
        entities=[],
        caption=caption,
        photo=[
            {
                "file_id": f"small_{user}",
                "file_unique_id": f"unique_small_{user}",
                "width": 100,
                "height": 100,
            },
            {
                "file_id": file_id or f"photo_{user}",
                "file_unique_id": f"unique_{user}",
                "width": 800,
                "height": 600,
            },
        ],
    )
    return update.__class__.model_validate(data)


async def photos(app):
    feed, _, runtime = app
    game = await collecting(app, "memory", (1, 2, 3))
    for user in (1, 2, 3):
        await feed(photo(user, f"Yashirin <izoh> & {user}", 1000 + user))
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


def test_memory_pure_rewards_require_another_correct_guesser_and_visible_sender():
    assert guess_rewards("1", {}, kind="memory") == {}
    assert guess_rewards("1", {"1": "1"}, kind="memory") == {}
    assert guess_rewards("1", {"2": "1", "3": "1"}, kind="memory") == {"2": 3, "3": 3, "1": 2}
    assert guess_rewards("1", {"2": "1"}, True, "memory") == {"2": 3}


async def test_memory_full_game_spoiler_hidden_caption_and_exact_points(media_app, sessions):
    _, transport, runtime = media_app
    game = await photos(media_app)
    game_id, old_query = game.id, None
    expected = 0
    while game:
        author = game.state["item"]
        others = [int(user) for user in game.state["players"] if user != author]
        assert (
            await runtime.guess_games.callback(vote_query(game, int(author), author))
            == texts.PRIVATE_GUESS_DENIED
        )
        if game.state["round"] == 1:
            for user in others:
                assert (
                    await runtime.guess_games.callback(vote_query(game, user, author))
                    == texts.PRIVATE_GUESS_SAVED
                )
            expected += 8
        elif game.state["round"] == 3:
            assert (
                await runtime.guess_games.callback(vote_query(game, others[0], author))
                == texts.PRIVATE_GUESS_SAVED
            )
            assert (
                await runtime.guess_games.callback(vote_query(game, others[0], author))
                == texts.PRIVATE_GAME_CLOSED
            )
            expected += 5
        if old_query:
            assert await runtime.guess_games.callback(old_query) == texts.PRIVATE_GAME_CLOSED
        old_query = vote_query(game, others[0], author)
        current = runtime.game_cache.get(game_id)
        await asyncio.gather(
            runtime.game_hub.advance(current, current.phase_deadline_at),
            runtime.game_hub.advance(current, current.phase_deadline_at),
        )
        await runtime.effects.drain()
        game = runtime.game_cache.get(game_id)
    async with sessions() as session:
        stored = await session.get(GameSession, game_id)
        assert stored.status == "finished"
        assert await session.scalar(select(func.sum(PointEvent.delta))) == expected == 13
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 5
        for user, item in stored.state["items"].items():
            assert item["file_id"] == f"photo_{user}"
            assert not {"photo", "file_unique_id", "width", "height", "bytes", "url"}.intersection(
                item
            )
    posted = [method for method in transport.methods if isinstance(method, SendPhoto)]
    assert len(posted) == 3 and all(method.has_spoiler is True for method in posted)
    assert all(
        "Yashirin" not in method.caption
        and "&lt;izoh&gt;" not in method.caption
        and "Yuboruvchi:" not in method.caption
        for method in posted
    )
    reveals = [
        method
        for method in transport.methods
        if isinstance(method, EditMessageCaption) and "Yuboruvchi:" in method.caption
    ]
    assert len(reveals) == 3 and all(
        "Yashirin &lt;izoh&gt; &amp;" in method.caption for method in reveals
    )
    assert all(
        method.reply_markup.inline_keyboard[-1][0].callback_data.startswith(f"ph:{game_id}:")
        for method in posted
    )
    assert not runtime.private_contexts.users


@pytest.mark.parametrize(
    "case", ["link", "mention", "long", "voice", "text", "forward", "edit", "bot", "old"]
)
async def test_memory_private_submission_guards(media_app, case):
    runtime = media_app[2]
    game = await collecting(media_app, "memory", (1, 2, 3))
    message = photo().message
    if case in {"link", "mention", "long"}:
        message = photo(
            caption={"link": "https://example.uz", "mention": "@kimdir", "long": "a" * 301}[case]
        ).message
    elif case == "voice":
        message = voice(1).message
    elif case == "text":
        message = dm_update("Matn").message
    elif case == "forward":
        message = message.model_copy(
            update={
                "forward_origin": MessageOriginHiddenUser(date=utc_now(), sender_user_name="Kimdir")
            }
        )
    elif case == "edit":
        message = message.model_copy(update={"edit_date": utc_now()})
    elif case == "bot":
        message = message.model_copy(update={"from_user": tg_user(1, True)})
    else:
        message = message.model_copy(update={"date": utc_now() - timedelta(days=1)})
    assert await runtime.guess_games.private_input(game, message) in {
        texts.PRIVATE_GAME_INVALID,
        texts.PRIVATE_GAME_INPUT_WAIT,
    }
    assert not runtime.game_cache.get(game.id).state["items"]


async def test_memory_duplicate_photo_callbacks_context_and_consent(media_app):
    feed, transport, runtime = media_app
    game = await collecting(media_app, "memory", (1, 2, 3))
    await asyncio.gather(feed(photo()), feed(photo(file_id="replacement", message_id=1001)))
    assert len(runtime.game_cache.get(game.id).state["items"]) == 1
    for user in (2, 3):
        await feed(photo(user, message_id=1000 + user))
    await runtime.effects.drain()
    game = runtime.game_cache.get(game.id)
    author = game.state["item"]
    other = next(int(user) for user in game.state["players"] if user != author)
    query = vote_query(game, other, author)
    invalid = [
        vote_query(game, other, author, round_number=0),
        vote_query(game, other, author, message_id=1),
        vote_query(game, 999, author),
        query.model_copy(update={"from_user": tg_user(other, True)}),
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
    await runtime.private_games.start(command_update("/yashirin", 1800).message)
    secret = runtime.game_cache.background(-1)
    assert (
        await runtime.private_games.join(secret.id, tg_user(1), "secret") == texts.PRIVATE_GAME_BUSY
    )
    assert any(
        "rozilik" in method.text and "spoiler" in method.text
        for method in transport.methods
        if hasattr(method, "text") and method.text
    )


async def test_memory_hidden_before_and_after_author_bonus(media_app, sessions):
    _, transport, runtime = media_app
    game = await photos(media_app)
    first = game.state["item"]
    first_message = game.state["items"][first]["message_id"]
    admin = callback(f"ph:{game.id}:{first}", 42).callback_query
    admin = admin.model_copy(
        update={"message": admin.message.model_copy(update={"message_id": first_message})}
    )
    assert (
        await runtime.private_games.hide(admin.model_copy(update={"from_user": tg_user(1)}))
        == texts.PRIVATE_GAME_HIDE_DENIED
    )
    assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_HIDE_DONE
    await runtime.effects.drain()
    while current := runtime.game_cache.get(game.id):
        author = current.state["item"]
        if author != first:
            voter = next(int(user) for user in current.state["players"] if user != author)
            assert (
                await runtime.guess_games.callback(vote_query(current, voter, author))
                == texts.PRIVATE_GUESS_SAVED
            )
        await runtime.game_hub.advance(runtime.game_cache.get(game.id), current.phase_deadline_at)
        await runtime.effects.drain()
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.state["items"][first]["author_points"] == 0
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 10
        other_id, other_item = next(
            (key, item) for key, item in row.state["items"].items() if key != first
        )
    late = admin.model_copy(
        update={
            "data": f"ph:{game.id}:{other_id}",
            "message": admin.message.model_copy(update={"message_id": other_item["message_id"]}),
        }
    )
    member = ChatMemberMember(user=tg_user(runtime.game_hub.bot.id, True))
    with patch.object(runtime.game_hub.bot, "get_chat_member", new=AsyncMock(return_value=member)):
        assert await runtime.private_games.hide(late) == texts.PRIVATE_GAME_HIDE_MEDIA
    assert await runtime.private_games.hide(late) == texts.PRIVATE_GAME_CLOSED
    await runtime.effects.drain()
    async with sessions() as session:
        assert await session.scalar(select(func.sum(PointEvent.delta))) == 8
    assert any(
        isinstance(method, DeleteMessage) and method.message_id == first_message
        for method in transport.methods
    )
    assert not any(
        isinstance(method, EditMessageCaption)
        and method.message_id == first_message
        and "Yuboruvchi:" in method.caption
        for method in transport.methods
    )


async def test_memory_collection_lobby_and_single_photo_timeouts(media_app):
    feed, _, runtime = media_app
    empty = await collecting(media_app, "memory", (1, 2, 3))
    await runtime.game_hub.advance(empty, empty.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(empty.id) is None
    small = await lobby(media_app, "memory", (1, 2))
    await runtime.game_hub.advance(small, small.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(small.id) is None
    game = await collecting(media_app, "memory", (1, 2, 3))
    await feed(photo())
    game = runtime.game_cache.get(game.id)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    current = runtime.game_cache.get(game.id)
    assert len(current.state["order"]) == 1
    await runtime.game_hub.advance(current, current.phase_deadline_at)
    await runtime.effects.drain()
    assert not runtime.private_contexts.users


@pytest.mark.parametrize("action", ["stop", "restart", "migration", "erasure", "leave"])
async def test_memory_lifecycle_erases_file_ids_and_captions(media_app, sessions, action):
    feed, _, runtime = media_app
    game = await collecting(media_app, "memory", (1, 2, 3))
    await feed(photo(caption="Maxfiy izoh"))
    if action == "stop":
        assert await runtime.game_hub.stop(-1, 1) is None
    elif action == "restart":
        await runtime.guess_games.recover(runtime.game_cache.get(game.id))
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


async def test_erasure_cancels_inflight_photo_disclosure(media_app, sessions):
    feed, transport, runtime = media_app
    game = await collecting(media_app, "memory", (1, 2, 3))
    await feed(photo(1))
    await feed(photo(2))
    started, release = asyncio.Event(), asyncio.Event()
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, SendPhoto):
            started.set()
            await release.wait()
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        await feed(photo(3))
        await asyncio.wait_for(started.wait(), 2)
        try:
            assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
        finally:
            release.set()
        await runtime.effects.drain()
    assert not any(isinstance(method, SendPhoto) for method in transport.methods)
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).state == {"erased": True}


async def test_memory_send_watchdog_releases_context_without_late_photo(media_app):
    feed, transport, runtime = media_app
    game = await collecting(media_app, "memory", (1, 2, 3))
    await feed(photo(1))
    await feed(photo(2))
    started, release = asyncio.Event(), asyncio.Event()
    original = runtime.guess_games.send_answer

    async def delayed(snapshot):
        started.set()
        await release.wait()
        await original(snapshot)

    with patch.object(runtime.guess_games, "send_answer", side_effect=delayed):
        await feed(photo(3))
        await asyncio.wait_for(started.wait(), 2)
        current = runtime.game_cache.get(game.id)
        try:
            await runtime.game_hub.advance(current, current.phase_deadline_at)
            assert not runtime.private_contexts.users
        finally:
            release.set()
        await runtime.effects.drain()
    assert not any(isinstance(method, SendPhoto) for method in transport.methods)


def test_new_games_are_discoverable_and_help_fits_telegram():
    for command in ("yashirin", "fosh", "kimaytdi", "telefon", "eslaysizmi"):
        assert command in texts.GROUP_COMMANDS
        assert f"/{command}" in texts.GAME_CATALOG
        assert f"/{command}" in texts.help_text("oqibat.test")
        assert f"/{command}" in texts.WEB_COPY["rules"]
    assert len(texts.help_text("oqibat.test")) < 4096


async def test_memory_lobby_caps_at_ten_and_eleventh_user_keeps_context_free(media_app):
    runtime = media_app[2]
    game = await lobby(media_app, "memory", tuple(range(1, 12)))
    assert len(game.state["players"]) == 10
    assert "11" not in game.state["players"] and runtime.private_contexts.get(11) is None


async def test_memory_requires_delete_permission(guess_app):
    runtime = guess_app[2]
    assert (
        await runtime.private_games.start(command_update("/eslaysizmi").message, "memory")
        == texts.PRIVATE_GAME_NEED_DELETE
    )
    assert not runtime.game_cache.for_chat(-1)


async def test_legacy_photo_origin_backfill_and_old_hide_button_after_migration(media_app):
    runtime = media_app[2]
    game = await photos(media_app)
    game_id = game.id
    while current := runtime.game_cache.get(game_id):
        await runtime.game_hub.advance(current, current.phase_deadline_at)
        await runtime.effects.drain()

    def legacy(row):
        for item in row.state["items"].values():
            item.pop("origin_chat_id", None)

    assert await runtime.games.change(-1, game_id, legacy)
    await runtime.migrations.migrate(-1, -1001234)
    async with runtime.sessions() as session:
        row = await session.get(GameSession, game_id)
        item_id, item = next(iter(row.state["items"].items()))
        assert item["origin_chat_id"] == -1 and row.chat_id == -1001234
    admin = callback(f"ph:{game_id}:{item_id}", 42).callback_query
    admin = admin.model_copy(
        update={
            "message": admin.message.model_copy(
                update={
                    "message_id": item["message_id"],
                    "chat": admin.message.chat.model_copy(update={"id": -1001234}),
                }
            )
        }
    )
    assert await runtime.private_games.hide(admin) == texts.PRIVATE_GAME_CLOSED
