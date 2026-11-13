import asyncio
import json
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from string import Formatter
from types import SimpleNamespace

import pytest

from bot import texts
from bot.services.effects import Effects
from bot.utils.presentation import compact_html, units


class Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.open = [], []

    def handle_starttag(self, tag, attrs):
        self.open.append(tag)

    def handle_endtag(self, tag):
        assert self.open.pop() == tag

    def handle_data(self, data):
        self.parts.append(data)


@pytest.mark.parametrize("kind", texts.GAME_STYLE)
def test_all_game_boards_share_layout_timezone_and_keep_secrets(kind):
    game = SimpleNamespace(
        id=1,
        game=kind,
        status="running",
        started_by=1,
        phase_deadline_at=datetime(2026, 11, 13, 9, 32, tzinfo=UTC),
        state={
            "phase": "playing",
            "round": 3,
            "players": {"1": "<Ali> & G‘ani"},
            "display_tz": "Asia/Tashkent",
            "words": {"1": "SECRET_WORD"},
            "roles": {"1": "SECRET_ROLE"},
            "order": ["1"],
            "turn": 0,
        },
    )
    result = texts.board_layout(game, "Savolni o‘qib, tanlov qiling.")
    assert result.startswith(texts.game_title(kind))
    assert "Holat:" in result and ("▱" in result or "▰" in result)
    assert "⏳ 14:32 gacha" in result and "⏳ &lt;Ali&gt; &amp; G‘ani" in result
    assert "SECRET_WORD" not in result and "SECRET_ROLE" not in result
    assert texts.board_layout(game, result) == result
    assert game.state["words"]["1"] == "SECRET_WORD"


@pytest.mark.parametrize("limit", [1024, 4096])
def test_html_limits_preserve_tags_entities_and_utf16(limit):
    result = compact_html(
        '<b><a href="tg://user?id=1">' + "😀 &amp; &lt;script&gt; " * 2000 + "</a></b>", limit
    )
    parser = Plain()
    parser.feed(result)
    assert not parser.open and units("".join(parser.parts)) <= limit
    assert "<script>" not in result
    assert result.endswith("…</a></b>")


def test_progress_and_results_are_presentational_only():
    assert texts.progress_bar(3, 5) == "▰▰▰▱▱ 3/5"
    game = SimpleNamespace(
        game="math",
        id=5,
        status="finished",
        started_by=1,
        phase_deadline_at=None,
        state={
            "phase": "done",
            "round": 5,
            "names": {"1": "Ali", "2": "Vali", "3": "G‘ani"},
            "scores": {"1": 2, "2": 6, "3": 4},
        },
    )
    result = texts.board_layout(game, "Tugadi.")
    assert "5/5" in result and "🥇 Vali · 6 ball" in result
    assert "🥈 G‘ani · 4 ball" in result and "🥉 Ali · 2 ball" in result
    assert game.state["scores"] == {"1": 2, "2": 6, "3": 4}


def test_existing_template_placeholder_contracts_preserved():
    contracts = json.loads(
        (Path(__file__).parent / "fixtures/text_placeholders.json").read_text("utf-8")
    )
    for path, expected in contracts.items():
        name, *keys = path.split(".")
        value = getattr(texts, name)
        for key in keys:
            value = value[key]
        actual = sorted(field for _, field, _, _ in Formatter().parse(value) if field is not None)
        assert actual == expected, path


@pytest.mark.parametrize("role", texts.MAFIA_ROLE_CARDS)
def test_every_mafia_role_has_private_card_goal(role):
    card = texts.mafia_role_card(role)
    assert texts.MAFIA_ROLE_NAMES[role] in card and "Maqsad:" in card
    assert len(card) < 500


async def test_completed_effects_yield_to_cleanup_and_dependent_tasks():
    effects, seen = Effects(), []

    async def child():
        seen.append("child")

    async def parent():
        seen.append("parent")
        effects.start(child())

    effects.start(parent())
    await asyncio.wait_for(effects.drain(), timeout=2)
    assert seen == ["parent", "child"] and not effects.tasks
