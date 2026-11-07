import asyncio
import re
import threading
import time
from datetime import date
from html import unescape
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import Message
from PIL import Image, ImageFont
from test_easy_games import game_app as game_app
from test_weekly import weekly_app as weekly_app

from bot import texts
from bot.db.models import GameSession
from bot.services.cards import FONT, SIZE, fit_text, plain_line, render_card
from bot.services.game_cache import view
from bot.services.sender import Priority
from bot.utils.time import utc_now


def test_bundled_font_license_and_uzbek_glyphs():
    assert "SIL OPEN FONT LICENSE" in FONT.with_name("OFL.txt").read_text(encoding="utf-8")
    font = ImageFont.truetype(str(FONT), 32)
    missing = bytes(font.getmask("\u0378"))
    for char in "ʻʼ‘ЎўҒғҚқҲҳ":
        assert bytes(font.getmask(char)) != missing
    assert plain_line("A\u202eB\x00") == "AB"
    shortened = fit_text("Oʻzbekiston " * 100, font, 100)
    assert shortened.endswith("…") and font.getlength(shortened) <= 100


def test_renderer_outputs_valid_rgb_png_with_empty_and_long_names():
    for rows in ([], [("Oʻtkir Gʻulomov " * 30, 123), ("Ўзбекистон <&>", -3)]):
        png = render_card(texts.CARD_WEEKLY_TITLE, rows, "oqibat.test", "oʻ gʻ oʼ gʼ")
        with Image.open(BytesIO(png)) as image:
            assert image.size == SIZE and image.mode == "RGB" and image.format == "PNG"
            assert image.getextrema()[0][0] != image.getextrema()[0][1]


@pytest.mark.parametrize(
    "kind,state,expected",
    [
        ("duel", {"winner": 1, "names": {"1": "User"}}, [("User", 2)]),
        ("quiz", {"scores": {"1": 5}, "names": {"1": "User"}}, [("User", 5)]),
        ("krokodil", {"scores": {"1": -3}, "names": {"1": "User"}}, None),
        ("hyj", {"result": "truth_done", "name": "User"}, [("User", 5)]),
        ("hyj", {"result": "dare_done", "name": "User", "result_points": 15}, [("User", 15)]),
        ("hyj", {"result": "refused", "name": "User"}, None),
        ("wyr", {}, None),
        (
            "mafia",
            {
                "winner": "town",
                "roles": {"1": "town", "2": "mafia"},
                "players": {"1": "User", "2": "Other"},
                "alive": ["1"],
            },
            [("User", 13)],
        ),
        ("mafia", {"winner": "draw"}, None),
    ],
)
def test_card_data_only_for_finished_winners(kind, state, expected):
    game = SimpleNamespace(game=kind, status="finished", state=state)
    data = texts.game_card_data(game)
    assert (data["rows"] if data else None) == expected
    game.status = "running"
    assert texts.game_card_data(game) is None


def test_compact_weekly_caption_stays_below_telegram_limit_and_escapes_names():
    name = "<&>" * 200
    data = {
        "top": [(user, name, 9223372036854775807) for user in range(1, 6)],
        "active": (1, name, 1000000),
        "done": 1000,
        "missed": 1000,
        "pending": 1000,
    }
    caption = texts.weekly_summary(date(2026, 11, 2), data, "a" * 30, compact=True)
    assert "&lt;" in caption
    assert len(unescape(re.sub(r"<[^>]+>", "", caption))) < 1024


async def finished_duel(runtime, sessions):
    game_id = await runtime.games.create(
        -1,
        game="duel",
        status="finished",
        started_by=1,
        state={"winner": 1, "names": {"1": "Oʻtkir"}},
    )
    async with sessions() as session:
        return view(await session.get(GameSession, game_id))


def photo_transport(transport):
    original = transport.make_request

    async def request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, SendPhoto):
            transport.methods.append(method)
            assert method.photo.data.startswith(b"\x89PNG")
            return Message(
                message_id=777,
                date=utc_now(),
                chat={"id": method.chat_id, "type": "supergroup"},
                photo=[{"file_id": "test", "file_unique_id": "test", "width": 1000, "height": 820}],
            )
        return await original(bot, method, timeout)

    return request


async def test_game_card_once_claim_audit_and_game_priority(game_app, sessions):
    feed, transport, runtime = game_app
    runtime.cards.enabled = True
    game = await finished_duel(runtime, sessions)
    with (
        patch.object(transport, "make_request", side_effect=photo_transport(transport)),
        patch.object(runtime.sender, "send", wraps=runtime.sender.send) as queued,
    ):
        await asyncio.gather(runtime.cards.game(game), runtime.cards.game(game))
        assert queued.call_args.kwargs["priority"] == Priority.GAME
    assert len([m for m in transport.methods if isinstance(m, SendPhoto)]) == 1
    async with sessions() as session:
        state = (await session.get(GameSession, game.id)).state
        assert state["result_card_claimed"] and state["result_card_status"] == "sent"
        assert state["result_card_message_id"] == 777


async def test_weekly_card_is_one_bulk_post_with_complete_caption_and_button(weekly_app):
    feed, transport, runtime, due = weekly_app
    runtime.cards.enabled = True
    with (
        patch.object(transport, "make_request", side_effect=photo_transport(transport)),
        patch.object(runtime.sender, "send", wraps=runtime.sender.send) as queued,
    ):
        await runtime.scheduler.tick(due)
        assert queued.call_args.kwargs["priority"] == Priority.BULK
    photo = [m for m in transport.methods if isinstance(m, SendPhoto)]
    assert len(photo) == 1 and "Hafta vazifalari" in photo[0].caption
    assert "Muallif: @oqibat.test" in photo[0].caption
    assert "startgroup=add" in photo[0].reply_markup.inline_keyboard[0][0].url


async def test_font_failure_keeps_weekly_text_and_records_failed_game_card(weekly_app, sessions):
    feed, transport, runtime, due = weekly_app
    runtime.cards.enabled = True
    with patch("bot.services.result_cards.render_card", side_effect=OSError("missing font")):
        await runtime.scheduler.tick(due)
        assert isinstance(transport.methods[-1], SendMessage)
        assert "Haftalik oqibat" in transport.methods[-1].text
        game = await finished_duel(runtime, sessions)
        await runtime.cards.game(game)
    async with sessions() as session:
        assert (await session.get(GameSession, game.id)).state["result_card_status"] == "failed"


async def test_rendering_is_off_loop_and_bounded_to_two_workers(game_app):
    feed, transport, runtime = game_app
    runtime.cards.enabled = True
    mutex = threading.Lock()
    active = peak = 0

    def render(*args):
        nonlocal active, peak
        with mutex:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with mutex:
            active -= 1
        return b"test"

    with patch("bot.services.result_cards.render_card", side_effect=render):
        results = await asyncio.gather(*[runtime.cards.render("Test", []) for _ in range(8)])
    assert peak == 2 and results == [b"test"] * 8
