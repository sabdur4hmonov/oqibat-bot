import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import (
    DeleteMessage,
    EditMessageText,
    GetChatMember,
    PinChatMessage,
    SendDice,
    SendMessage,
    SendPhoto,
    SendPoll,
    UnpinChatMessage,
)
from aiogram.types import Message
from sqlalchemy import func, select
from test_challenge_flows import command_update
from test_easy_games import game_app as game_app
from test_group_flows import administrator, callback, tg_user

from bot import texts
from bot.db.models import Challenge, Chat, GameSession, Membership, PointEvent
from bot.games import number_hunt
from bot.utils.game_timers import scale_times
from bot.utils.time import utc_now
from scripts import smoke_live


@pytest.mark.parametrize("kind", texts.GAME_STYLE)
def test_deadline_policy_every_kind_caps_windows_and_production_identity(kind):
    now = datetime(2026, 11, 13, tzinfo=UTC)
    end = now + timedelta(seconds=300)
    state = {
        "timer_multiplier": 0.1,
        "end_at": end.isoformat(),
        "answer_until": end.isoformat(),
        "hard_deadline": (now + timedelta(hours=1)).isoformat(),
        "input_from": now.isoformat(),
    }
    row = SimpleNamespace(game=kind, state=state, phase_deadline_at=end)
    scale_times(row, {}, None, now)
    assert row.phase_deadline_at == now + timedelta(seconds=30)
    assert row.state["end_at"] == row.state["answer_until"] == row.phase_deadline_at.isoformat()
    assert datetime.fromisoformat(row.state["hard_deadline"]) == now + timedelta(minutes=6)
    assert row.state["input_from"] == now.isoformat()
    previous = deepcopy(row.state)
    row.phase_deadline_at = datetime.fromisoformat(row.state["hard_deadline"])
    scale_times(row, previous, now + timedelta(seconds=30), now + timedelta(seconds=30))
    assert row.phase_deadline_at == datetime.fromisoformat(previous["hard_deadline"])
    assert row.state == previous
    normal = SimpleNamespace(game=kind, state={"timer_multiplier": 1}, phase_deadline_at=end)
    scale_times(normal, {}, None, now)
    assert normal.phase_deadline_at is end and normal.state == {"timer_multiplier": 1}


def test_accusation_cooldown_and_number_wait_scale_without_changing_points():
    now = datetime(2026, 11, 13, tzinfo=UTC)
    row = SimpleNamespace(
        game="secret",
        state={"timer_multiplier": 0.1, "cooldowns": {"1": (now + timedelta(hours=1)).timestamp()}},
        phase_deadline_at=None,
    )
    scale_times(row, {}, None, now)
    assert row.state["cooldowns"]["1"] == (now + timedelta(minutes=6)).timestamp()
    state = number_hunt.initial(50)
    state.update(phase="playing", timer_multiplier=0.1)
    state = number_hunt.guess(state, 1, "Ali", 10, 101, 1000)
    assert number_hunt.guess(state, 1, "Ali", 20, 102, 1000.1) is None
    assert number_hunt.guess(state, 1, "Ali", 20, 102, 1000.31) is not None


async def enable(runtime):
    runtime.owner_tools.owner_id = 42
    message = command_update("/tezrejim on", user_id=42).message
    assert await runtime.live_tools.fast(message, "on") == texts.FAST_ON
    return message


@pytest.mark.parametrize(
    "kind,seconds",
    [
        ("duel", 9),
        ("rps", 9),
        ("quiz", 3),
        ("wyr", 6),
        ("number", 18),
        ("math", 2),
        ("krokodil", 18),
        ("hyj", 9),
        ("mafia", 9),
        ("secret", 30),
        ("kim", 18),
        ("telephone", 18),
        ("memory", 30),
    ],
)
async def test_actual_game_starts_use_chat_test_factor_and_visible_mark(game_app, kind, seconds):
    _, transport, runtime = game_app
    await enable(runtime)
    message = command_update("/game").message
    if kind in {"secret", "kim", "telephone", "memory"}:
        service = runtime.private_games
        with patch.object(service, "can_delete", AsyncMock(return_value=True)):
            assert await service.start(message, kind) is None
    else:
        service = runtime.game_hub.services[kind]
        args = (message, kind) if kind in {"duel", "quiz", "wyr", "number", "math"} else (message,)
        assert await service.start(*args) is None
    await runtime.effects.drain()
    game = (
        runtime.game_cache.background(-1)
        if kind == "secret"
        else runtime.game_cache.for_chat(-1)[0]
    )
    assert game.state["timer_multiplier"] == 0.1
    assert 0 < (game.phase_deadline_at - utc_now()).total_seconds() <= seconds + 0.5
    board = texts.board_layout(game, "Davom etamiz.")
    assert texts.FAST_BOARD in board and texts.board_layout(game, board) == board
    if kind == "quiz":
        assert [method for method in transport.methods if isinstance(method, SendPoll)][
            -1
        ].open_period == 5
    if kind == "mafia":
        cap = datetime.fromisoformat(game.state["hard_deadline"])
        assert 359 < (cap - datetime.fromisoformat(game.state["started_at"])).total_seconds() <= 361


async def test_owner_only_toggle_isolation_no_midgame_changes_and_persistent_migration(
    game_app, sessions
):
    _, _, runtime = game_app
    runtime.owner_tools.owner_id = 42
    stranger = command_update("/tezrejim on", user_id=1).message
    assert await runtime.live_tools.fast(stranger, "on") == texts.OWNER_ONLY
    assert runtime.live_tools.start(stranger) == texts.OWNER_ONLY
    before = await runtime.groups.get(-1)
    owner = await enable(runtime)
    assert await runtime.live_tools.fast(owner, "bad") == texts.FAST_USAGE
    after = await runtime.groups.get(-1)
    assert after.fast_mode and after.next_daily_at == before.next_daily_at
    async with sessions.begin() as session:
        session.add(Chat(id=-2, title="normal", bot_is_admin=True))
        await session.flush()
        session.add(Membership(chat_id=-2, user_id=1, opted_in=True, is_active=True))
    normal = stranger.model_copy(update={"chat": stranger.chat.model_copy(update={"id": -2})})
    runtime.participants.set(-2, 1, True)
    assert await runtime.quick_games.start(normal, "number") is None
    assert runtime.game_cache.main(-2).state["timer_multiplier"] == 1
    assert await runtime.quick_games.start(stranger, "math") is None
    assert await runtime.live_tools.fast(owner, "off") == texts.FAST_BUSY
    assert await runtime.game_hub.stop(-1, 1) is None
    await runtime.migrations.migrate(-1, -100999)
    async with sessions() as session:
        assert (await session.get(Chat, -100999)).fast_mode
        assert not (await session.get(Chat, -1)).is_active


async def test_linked_dare_uses_same_scaled_deadline_and_no_points(game_app, sessions):
    feed, _, runtime = game_app
    await enable(runtime)
    from datetime import time

    await runtime.groups.change_setting(-1, "quiet_start", time())
    await runtime.groups.change_setting(-1, "quiet_end", time())
    await feed(command_update("/hyj"))
    game = runtime.game_cache.main(-1)
    await feed(callback(f"hd:{game.id}", game.state["target"]))
    await runtime.effects.drain()
    async with sessions() as session:
        challenge = await session.scalar(select(Challenge))
        row = await session.get(GameSession, game.id)
        assert row.phase_deadline_at == challenge.deadline_at
        assert (challenge.deadline_at - challenge.created_at).total_seconds() == pytest.approx(360)
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0


async def test_fast_mafia_night_is_six_seconds_without_rescaling_existing_hard_cap(game_app):
    from test_mafia_flows import lobby

    runtime = game_app[2]
    await enable(runtime)
    game = await lobby(game_app, 5)
    cap = game.state["hard_deadline"]
    at = game.phase_deadline_at
    with (
        patch("bot.db.repo.games.utc_now", return_value=at),
        patch("bot.services.mafia.utc_now", return_value=at),
    ):
        await runtime.game_hub.advance(game, at)
        await runtime.effects.drain()
    night = runtime.game_cache.main(-1)
    assert night.state["phase"] == "night" and night.state["hard_deadline"] == cap
    assert (night.phase_deadline_at - at).total_seconds() == 6


@pytest.mark.parametrize("case", ["ok", "edit_failure", "no_rights"])
async def test_selftest_actions_owned_cleanup_failure_report_and_no_points(
    game_app, sessions, case
):
    _, transport, runtime = game_app
    runtime.owner_tools.owner_id = 42
    original = transport.make_request
    sequence = 1000

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        nonlocal sequence
        if isinstance(method, GetChatMember) and method.user_id == bot.id:
            transport.methods.append(method)
            return administrator(tg_user(bot.id, True)).model_copy(
                update={"can_delete_messages": case != "no_rights", "can_pin_messages": True}
            )
        if isinstance(method, (DeleteMessage, PinChatMessage, UnpinChatMessage)):
            transport.methods.append(method)
            return True
        if case == "edit_failure" and isinstance(method, EditMessageText):
            raise RuntimeError("synthetic failure")
        if isinstance(method, SendPhoto):
            transport.methods.append(method)
            sequence += 1
            return Message(
                message_id=sequence,
                date=utc_now(),
                chat={"id": -1, "type": "group"},
                photo=[
                    {"file_id": "fake", "file_unique_id": "fake", "width": 1080, "height": 1080}
                ],
            )
        sent = await original(bot, method, timeout)
        if isinstance(method, (SendMessage, SendPoll, SendDice)):
            sequence += 1
            sent = sent.model_copy(update={"message_id": sequence})
            if getattr(sent, "poll", None):
                transport.polls[sequence] = sent.poll
        return sent

    start = len(transport.methods)
    with patch.object(transport, "make_request", side_effect=request):
        message = command_update("/selftest", user_id=42).message
        assert runtime.live_tools.start(message) is None
        assert runtime.live_tools.start(message) == texts.SELFTEST_BUSY
        await runtime.effects.drain()
    methods = transport.methods[start:]
    report = [method for method in methods if isinstance(method, SendMessage)][-1].text
    assert ("❌" not in report) == (case == "ok")
    if case != "no_rights":
        assert sum(isinstance(method, SendPoll) for method in methods) == 2
        assert sum(isinstance(method, SendDice) for method in methods) == 1
        photos = [method for method in methods if isinstance(method, SendPhoto)]
        assert len(photos) == 2 and photos[0].has_spoiler
        pin = next(method for method in methods if isinstance(method, PinChatMessage))
        unpin = next(method for method in methods if isinstance(method, UnpinChatMessage))
        assert pin.message_id == unpin.message_id and pin.disable_notification
        assert {
            method.message_id for method in methods if isinstance(method, DeleteMessage)
        } == set(range(1001, 1007))
    else:
        assert not any(isinstance(method, SendPoll) for method in methods)
    assert not runtime.live_tools.active
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == 0
        assert await session.scalar(select(func.count()).select_from(GameSession)) == 0


async def test_pin_service_cleanup_deletes_only_known_bot_owned_notice_once(game_app):
    feed, transport, runtime = game_app
    runtime.live_tools.pin_targets[(-1, 1234)] = time.monotonic() + 60
    pinned = command_update("card", message_id=1234).message
    update = command_update("pin", message_id=1009, user_id=42)
    message = update.message.model_copy(update={"pinned_message": pinned, "text": None})
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, DeleteMessage):
            transport.methods.append(method)
            return True
        return await original(bot, method, timeout)

    with patch.object(transport, "make_request", side_effect=request):
        await feed(update.model_copy(update={"message": message}))
        assert (-1, 1234) in runtime.live_tools.pin_targets  # Human admin's pins are untouched.
        message = message.model_copy(update={"from_user": tg_user(runtime.game_hub.bot.id, True)})
        await feed(update.model_copy(update={"message": message}))
        await feed(update.model_copy(update={"message": message}))
        await runtime.effects.drain()
    deleted = [method for method in transport.methods if isinstance(method, DeleteMessage)]
    assert [(method.chat_id, method.message_id) for method in deleted] == [(-1, 1009)]


class Reply:
    def __init__(self, status=200, data=None):
        self.status, self.data = status, data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.data


@pytest.mark.parametrize("case", ["ok", "network", "unhealthy", "missing_url", "username"])
async def test_smoke_read_only_report_is_redacted_and_exit_status_meaningful(case):
    calls, output = [], []
    settings = SimpleNamespace(
        bot_username="TestBot",
        use_webhook=False,
        webhook_url=None,
        webapp_url="https://example.test/webapp" if case != "missing_url" else None,
    )
    bot = SimpleNamespace(
        get_me=AsyncMock(
            return_value=SimpleNamespace(
                is_bot=True, username="OtherBot" if case == "username" else "TestBot"
            )
        ),
        get_webhook_info=AsyncMock(return_value=SimpleNamespace(url="", last_error_date=None)),
    )

    def get(url, **kwargs):
        calls.append(url)
        assert kwargs["allow_redirects"] is False
        if case == "network":
            raise RuntimeError("TOKEN secret private user text")
        return Reply(
            503 if case == "unhealthy" and url.endswith("healthz") else 200,
            dict(status="ok", last_tick_age_seconds=20, send_queue_length=0),
        )

    assert await smoke_live.check(settings, bot, SimpleNamespace(get=get), output.append) == (
        case == "ok"
    )
    assert output[-1] == (texts.SMOKE_OK if case == "ok" else texts.SMOKE_BAD)
    assert all(word not in "\n".join(output) for word in ("TOKEN", "secret", "private user text"))
    assert (
        smoke_live.health_url("https://example.test/webapp?q=1") == "https://example.test/healthz"
    )
    with pytest.raises(ValueError):
        smoke_live.health_url("http://example.test/webapp")
