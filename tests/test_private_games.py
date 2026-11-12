import asyncio
import random
from datetime import timedelta
from unittest.mock import patch

import pytest
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from sqlalchemy import event, func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user

from bot import texts
from bot.db.models import Chat, GameSession, PointEvent
from bot.db.repo.games import Award, GameBusy
from bot.games.private_input import (
    matches,
    parse_payload,
    payload,
    repair_cycle,
    safe_submission,
    target_cycle,
)
from bot.utils.time import utc_now


def dm_update(text, user=1, message_id=200, **media):
    update = command_update(text if text.strip() else "empty", message_id, user)
    values = {"chat": {"id": user, "type": "private"}, "text": text, **media}
    return update.__class__.model_validate(
        {**update.model_dump(), "message": {**update.message.model_dump(), **values}}
    )


def group_message(text, user=1, message_id=300, **values):
    return command_update(text, message_id, user).message.model_copy(
        update={"date": utc_now(), **values}
    )


async def lobby(app, kind="secret", users=(1, 2, 3)):
    feed, _, runtime = app
    command = {"secret": "yashirin", "kim": "kimaytdi"}.get(kind, kind)
    await feed(command_update(f"/{command}"))
    game = next(game for game in runtime.game_cache.for_chat(-1) if game.game == kind)
    for user in users:
        if not runtime.participants.contains(-1, user):
            await runtime.groups.membership(-1, tg_user(user), opted_in=True)
        await feed(dm_update(f"/start {payload(kind, game.id)}", user))
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


async def secret_game(app, users=(1, 2, 3)):
    runtime = app[2]
    runtime.content.banks["secret_words"] = [
        {"key": str(i), "word": word}
        for i, word in enumerate(["palov", "choy", "kitob", "maktab", "osmon", "daraxt", "sayohat"])
    ]
    game = await lobby(app, users=users)
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    return runtime.game_cache.get(game.id)


def test_deep_links_bounded_and_cycle_is_single_and_repairable():
    for kind in ("mafia", "secret", "kim", "telephone", "memory"):
        assert parse_payload(payload(kind, 123)) == (kind, 123)
    for value in ("secret_1", "yashirin_-1", "yashirin_0", "mafia_１", "mafia_" + "1" * 65):
        assert parse_payload(value) is None
    for count in range(3, 21):
        players = list(map(str, range(count)))
        cycle = target_cycle(players, random.Random(count))
        assert set(cycle) == set(cycle.values()) == set(players)
        seen, cursor = [], players[0]
        while cursor not in seen:
            seen.append(cursor)
            cursor = cycle[cursor]
        assert len(seen) == count and all(user != target for user, target in cycle.items())
        repaired = repair_cycle(seen[1:])
        assert set(repaired) == set(players) - {seen[0]}


@pytest.mark.parametrize(
    ("word", "value", "expected"),
    [
        ("palov", "PALOVDAN", True),
        ("palov", "palovni", True),
        ("choy", "чойлар", True),
        ("uy", "uylar", False),
        ("uy", "uy", True),
        ("palov", "oshpalov", False),
        ("o‘rik", "ЎРИК", True),
    ],
)
def test_secret_token_matching(word, value, expected):
    assert matches(word, value) is expected


@pytest.mark.parametrize(
    "value", ["https://example.com", "@test", "t.me/test", "example.uz", "www.example.com"]
)
def test_private_submissions_reject_links_mentions_and_limit(value):
    assert not safe_submission(dm_update(value).message)
    assert not safe_submission(dm_update("a" * 301).message)
    assert safe_submission(dm_update("<b>O‘rik</b>").message)


async def test_secret_full_flow_cap_replacement_exact_points_and_finish(game_app, sessions):
    game = await secret_game(game_app)
    runtime = game_app[2]
    assert game.state["phase"] == "hunt" and len(set(game.state["words"].values())) == 3
    hunter = next(iter(game.state["players"]))
    target = int(game.state["targets"][hunter])
    for index in range(3):
        word = game.state["words"][hunter]
        message = group_message(word, target, 300 + index)
        await asyncio.gather(runtime.game_hub.observe(message), runtime.game_hub.observe(message))
        await runtime.effects.drain()
        game = runtime.game_cache.get(game.id)
        assert game.state["successes"][hunter] == index + 1
        assert game.state["words"][hunter] != word
    assert game.state["words"][hunter] is None
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.sum(PointEvent.delta)).where(PointEvent.reason == "secret_success")
            )
            == 30
        )
    await runtime.game_hub.advance(game, game.phase_deadline_at)
    await runtime.effects.drain()
    assert not runtime.game_cache.get(game.id) and not runtime.private_contexts.users
    assert not runtime.private_games.words


async def test_secret_accusations_correct_wrong_cooldown_and_duplicate(game_app, sessions):
    game = await secret_game(game_app)
    runtime = game_app[2]
    accuser = "1"
    hunter = next(user for user, target in game.state["targets"].items() if target == accuser)
    reply = group_message("Salom", int(hunter))
    accusation = group_message("/fosh", 1, 350, reply_to_message=reply)
    assert await runtime.private_games.accuse(accusation) is None
    assert await runtime.private_games.accuse(accusation) == texts.SECRET_ACCUSE_LIMIT
    wrong = next(user for user in game.state["players"] if user not in {hunter, accuser})
    bad = group_message("/fosh", 1, 351, reply_to_message=group_message("Salom", int(wrong)))
    assert await runtime.private_games.accuse(bad) == texts.SECRET_WRONG
    assert (
        await runtime.private_games.accuse(bad.model_copy(update={"message_id": 352}))
        == texts.SECRET_ACCUSE_LIMIT
    )
    await runtime.effects.drain()
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.sum(PointEvent.delta)).where(PointEvent.reason == "secret_accuse")
            )
            == 3
        )


async def test_normal_forwarded_edited_nonmatching_messages_zero_sql(game_app, sessions):
    game = await secret_game(game_app)
    runtime = game_app[2]
    hunter = next(iter(game.state["words"]))
    target = int(game.state["targets"][hunter])
    statements = []
    engine = sessions.kw["bind"].sync_engine

    def record(*args):
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", record)
    try:
        await runtime.game_hub.observe(group_message("Oddiy salom", target))
        await runtime.game_hub.observe(
            group_message(game.state["words"][hunter], target, edit_date=utc_now())
        )
        await runtime.game_hub.observe(
            group_message(
                game.state["words"][hunter], target, forward_origin={"type": "hidden_user"}
            )
        )
        assert not statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


async def test_background_main_consent_context_rule_including_mafia(game_app, sessions):
    feed, transport, runtime = game_app
    game = await lobby(game_app)
    board = next(
        method
        for method in transport.methods
        if isinstance(method, SendMessage)
        and method.chat_id == -1
        and method.reply_markup
        and "Yashirin" in method.text
    )
    assert "rozilik" in board.text and "guruhga" in board.text
    assert all(button.url for button in board.reply_markup.inline_keyboard[0])
    await feed(command_update("/mafia"))
    mafia = runtime.game_cache.main(-1)
    assert mafia.game == "mafia" and runtime.game_cache.background(-1).id == game.id
    assert await runtime.mafia_game.join(mafia.id, tg_user(1)) == texts.PRIVATE_GAME_BUSY
    with pytest.raises(GameBusy):
        await runtime.games.start(
            -1, 1, "secret", {"phase": "lobby"}, utc_now() + timedelta(minutes=1)
        )
    await runtime.game_hub.cancel(game, defer=True)
    await runtime.effects.drain()
    assert await runtime.mafia_game.join(mafia.id, tg_user(1)) == texts.MAFIA_JOINED
    await feed(command_update("/yashirin", 360))
    new = runtime.game_cache.background(-1)
    assert await runtime.private_games.join(new.id, tg_user(1), "secret") == texts.PRIVATE_GAME_BUSY
    assert (
        await runtime.private_games.join(new.id, tg_user(2, True), "secret")
        == texts.PRIVATE_GAME_CLOSED
    )


async def test_secret_duration_stale_foreign_bot_and_insufficient_bank(game_app):
    feed, transport, runtime = game_app
    game = await lobby(game_app)
    await feed(callback(f"pg:{game.id}:0:h:2", 1))
    await runtime.effects.drain()
    assert runtime.game_cache.get(game.id).state["hours"] == 2
    for data, user in [
        (f"pg:{game.id}:1:h:6", 1),
        (f"pg:{game.id}:0:h:6", 2),
        (f"pg:{game.id}:bad:h:6", 1),
    ]:
        await feed(callback(data, user))
    query = callback(f"pg:{game.id}:0:h:6", 1).callback_query
    assert (
        await runtime.private_games.callback(
            query.model_copy(update={"from_user": tg_user(1, True)})
        )
        == texts.PRIVATE_GAME_CLOSED
    )
    assert (
        await runtime.private_games.callback(
            query.model_copy(
                update={"message": query.message.model_copy(update={"message_id": 999})}
            )
        )
        == texts.PRIVATE_GAME_CLOSED
    )
    await runtime.game_hub.advance(runtime.game_cache.get(game.id), game.phase_deadline_at)
    await runtime.effects.drain()
    assert runtime.game_cache.get(game.id) is None
    assert any(
        isinstance(method, EditMessageText) and texts.PRIVATE_GAME_NOT_ENOUGH == method.text
        for method in transport.methods
    )
    assert any(isinstance(method, AnswerCallbackQuery) for method in transport.methods)


async def test_secret_leave_repairs_cycle_then_cancel_below_minimum(game_app):
    game = await secret_game(game_app, (1, 2, 3, 42))
    runtime = game_app[2]
    await runtime.groups.membership(-1, tg_user(1), opted_in=False)
    await runtime.effects.drain()
    game = runtime.game_cache.get(game.id)
    assert set(game.state["targets"]) == set(game.state["targets"].values()) == {"2", "3", "42"}
    assert runtime.private_contexts.get(1) is None
    await runtime.groups.membership(-1, tg_user(2), active=False)
    await runtime.effects.drain()
    assert runtime.game_cache.get(game.id) is None and not runtime.private_games.words


async def test_secret_leave_during_private_delivery_repairs_before_play(game_app):
    runtime = game_app[2]
    runtime.content.banks["secret_words"] = [
        {"key": str(i), "word": word}
        for i, word in enumerate(["palov", "choy", "kitob", "maktab", "osmon"])
    ]
    game = await lobby(game_app, users=(1, 2, 3, 42))
    started, release = asyncio.Event(), asyncio.Event()
    original = runtime.private_games.secret_dm
    first = True

    async def delayed(snapshot, hunter):
        nonlocal first
        if first:
            first = False
            started.set()
            await release.wait()
        return await original(snapshot, hunter)

    with patch.object(runtime.private_games, "secret_dm", side_effect=delayed):
        await runtime.game_hub.advance(game, game.phase_deadline_at)
        await asyncio.wait_for(started.wait(), 2)
        try:
            await runtime.groups.membership(-1, tg_user(1), opted_in=False)
        finally:
            release.set()
        await runtime.effects.drain()
    current = runtime.game_cache.get(game.id)
    assert current.state["phase"] == "hunt"
    assert (
        set(current.state["targets"]) == set(current.state["targets"].values()) == {"2", "3", "42"}
    )
    assert "1" not in current.state["words"]


@pytest.mark.parametrize("action", ["restart", "migration", "erasure", "stop"])
async def test_secret_lifecycle_releases_contexts_and_stale_state(game_app, sessions, action):
    game = await secret_game(game_app)
    runtime = game_app[2]
    if action == "restart":
        await runtime.private_games.recover(game)
    elif action == "migration":
        await runtime.migrations.migrate(-1, -1001234)
    elif action == "erasure":
        assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
    else:
        assert await runtime.game_hub.stop(-1, 1) is None
    await runtime.effects.drain()
    assert not runtime.private_contexts.users and not runtime.private_games.words
    async with sessions() as session:
        row = await session.get(GameSession, game.id)
        assert row.status == "cancelled"
        if action == "erasure":
            assert row.state == {"erased": True}
        if action == "migration":
            assert row.chat_id == -1001234 and not (await session.get(Chat, -1)).is_active


async def test_admin_hide_author_points_reversed_once_foreign_and_nonadmin_rejected(
    game_app, sessions
):
    game = await secret_game(game_app)
    runtime = game_app[2]

    def material(row):
        row.state["items"]["1"] = {
            "user_id": 1,
            "kind": "text",
            "text": "Xotira",
            "message_id": 100,
            "author_points": 3,
        }
        row.state["scores"]["1"] = 3
        return [Award(1, 3, "private_author", f"game:{row.id}:1")]

    await runtime.games.transition(-1, game.id, material)
    query = callback(f"ph:{game.id}:1", 1).callback_query
    assert await runtime.private_games.hide(query) == texts.PRIVATE_GAME_HIDE_DENIED
    admin = callback(f"ph:{game.id}:1", 42).callback_query
    foreign = admin.model_copy(
        update={"message": admin.message.model_copy(update={"message_id": 555})}
    )
    assert await runtime.private_games.hide(foreign) == texts.PRIVATE_GAME_CLOSED
    results = await asyncio.gather(
        runtime.private_games.hide(admin), runtime.private_games.hide(admin)
    )
    assert results.count(texts.PRIVATE_GAME_HIDE_DONE) == 1
    await runtime.effects.drain()
    async with sessions() as session:
        assert (
            await session.scalar(
                select(func.sum(PointEvent.delta)).where(
                    PointEvent.reason.in_(["private_author", "private_hidden"])
                )
            )
            == 0
        )
        assert (await session.get(GameSession, game.id)).state["items"]["1"]["hidden"]
