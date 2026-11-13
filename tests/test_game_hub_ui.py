from datetime import date, time
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import AnswerCallbackQuery, SendMessage
from test_easy_games import game_app as game_app
from test_group_flows import callback, tg_user

from bot import texts
from bot.keyboards.hub import CATEGORIES, daily_keyboard, hub_keyboard
from bot.services.onboarding import setup_keyboard


def button(runtime, data, user=1, keyboard=None, chat=-1, message_id=100):
    query = callback(data, user).callback_query
    return query.model_copy(
        update={
            "message": query.message.model_copy(
                update={
                    "from_user": tg_user(runtime.game_hub.bot.id, True),
                    "reply_markup": keyboard or hub_keyboard("fast"),
                    "chat": query.message.chat.model_copy(update={"id": chat}),
                    "message_id": message_id,
                }
            )
        }
    )


def test_categories_cover_each_game_once_and_daily_is_stable_spread():
    games = [kind for values in CATEGORIES.values() for kind in values]
    assert len(games) == len(set(games)) == len(texts.GAME_STYLE)
    assert set(games) == set(texts.GAME_STYLE)
    assert len(hub_keyboard().inline_keyboard) == 4
    picked = set()
    for chat in range(-100, 0):
        first = daily_keyboard(chat, date(2026, 11, 13))
        assert first == daily_keyboard(chat, date(2026, 11, 13))
        picked.add(first.inline_keyboard[0][0].callback_data)
    assert len(picked) == 5
    assert texts.GROUP_MENU == (
        "oyinlar",
        "qoshilish",
        "men",
        "top",
        "yutuqlar",
        "sozlamalar",
        "stop",
        "help",
    )


@pytest.mark.parametrize("kind", texts.GAME_STYLE)
async def test_hub_reuses_existing_start_checks_with_human_actor(game_app, kind):
    _, transport, runtime = game_app
    if kind in {"secret", "kim", "telephone", "memory"}:
        service = runtime.private_games
    else:
        service = runtime.game_hub.services[kind]
    category = next(key for key, values in CATEGORIES.items() if kind in values)
    query = button(runtime, f"hg:{kind}", 2, hub_keyboard(category))
    with patch.object(service, "start", new_callable=AsyncMock, return_value=None) as start:
        await runtime.game_catalog.callback(query)
    message = start.await_args.args[0]
    assert message.from_user.id == 2 and not message.from_user.is_bot
    assert message.reply_to_message is None and message.sender_chat is None
    assert any(isinstance(method, AnswerCallbackQuery) for method in transport.methods)


async def test_hub_actual_membership_slot_guards_and_category_navigation(game_app):
    _, transport, runtime = game_app
    await runtime.game_catalog.callback(button(runtime, "hc:fast", keyboard=hub_keyboard()))
    assert transport.methods[-1].reply_markup == hub_keyboard("fast")
    await runtime.game_catalog.callback(button(runtime, "hg:math", 77))
    assert transport.methods[-1].text == texts.GAME_JOIN_FIRST
    assert runtime.game_cache.main(-1) is None
    await runtime.game_catalog.callback(button(runtime, "hg:math", 2))
    await runtime.effects.drain()
    game = runtime.game_cache.main(-1)
    assert game.game == "math" and game.started_by == 2
    await runtime.game_catalog.callback(button(runtime, "hg:quiz", 3))
    assert transport.methods[-1].text == texts.GAME_BUSY
    assert runtime.game_cache.main(-1).id == game.id


@pytest.mark.parametrize("case", ["bot", "foreign", "stale", "private"])
async def test_invalid_and_private_hub_does_not_start(game_app, case):
    _, transport, runtime = game_app
    query = button(runtime, "hg:math")
    if case == "bot":
        query = query.model_copy(update={"from_user": tg_user(1, True)})
    elif case == "foreign":
        query = query.model_copy(
            update={"message": query.message.model_copy(update={"from_user": tg_user(77)})}
        )
    elif case == "stale":
        query = query.model_copy(update={"data": "hg:mafia"})
    else:
        query = query.model_copy(
            update={
                "message": query.message.model_copy(
                    update={
                        "chat": query.message.chat.model_copy(update={"type": "private", "id": 1})
                    }
                )
            }
        )
    await runtime.game_catalog.callback(query)
    assert runtime.game_cache.main(-1) is None
    assert isinstance(transport.methods[-1], AnswerCallbackQuery)
    assert transport.methods[-1].show_alert


async def test_three_admin_steps_persist_and_reject_stale_duplicate_foreign(game_app):
    _, transport, runtime = game_app
    for step, choice in ((0, 2), (1, 3), (2, 0)):
        query = button(runtime, f"qs:{step}:{choice}", 42, setup_keyboard(step))
        await runtime.quick_setup.callback(query)
        assert transport.methods[-1].reply_markup == setup_keyboard(step + 1)
        await runtime.quick_setup.callback(query)
        assert runtime.quick_setup.pending[-1] == (100, step + 1)
    chat = await runtime.groups.get(-1)
    assert chat.daily_time == time(18) and chat.challenges_per_day == 3
    assert chat.penalty_mode == "off"
    runtime.quick_setup.remember(-1, 100)
    await runtime.quick_setup.callback(button(runtime, "qs:0:0", 1, setup_keyboard(0)))
    assert transport.methods[-1].text == texts.ADMINS_ONLY
    await runtime.quick_setup.callback(
        button(runtime, "qs:0:0", 42, setup_keyboard(0), message_id=101)
    )
    assert (await runtime.groups.get(-1)).daily_time == time(18)
    runtime.quick_setup.pending.clear()  # Restart loses navigation, never saved choices.
    await runtime.quick_setup.callback(button(runtime, "qs:0:0", 42, setup_keyboard(0)))
    assert (await runtime.groups.get(-1)).daily_time == time(18)


async def test_daily_suggestion_and_hub_command_are_wired(game_app):
    feed, transport, runtime = game_app
    from test_challenge_flows import command_update

    await feed(command_update("/oyinlar"))
    assert transport.methods[-1].reply_markup == hub_keyboard()
    chat = await runtime.groups.get(-1)
    from bot.utils.time import utc_now

    await runtime.daily.post(chat, utc_now())
    post = next(method for method in reversed(transport.methods) if isinstance(method, SendMessage))
    assert post.reply_markup.inline_keyboard[0][0].text == texts.DAILY_GAME
