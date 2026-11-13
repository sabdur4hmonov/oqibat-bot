import asyncio
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import func, select
from test_easy_games import game_app as game_app

from bot import texts
from bot.constants import LEVEL_THRESHOLDS
from bot.db.models import Achievement, Chat, PointEvent
from bot.services.avatars import Avatars, thumbnail
from bot.services.levels import level_for
from bot.services.webapp_data import achievements, leaderboard, profile


@pytest.mark.parametrize(
    "points,number,progress,remaining",
    [
        (-10, 1, 0, 60),
        (0, 1, 0, 50),
        (49, 1, 98, 1),
        (50, 2, 0, 150),
        (199, 2, 99, 1),
        (200, 3, 0, 800),
        (999, 3, 99, 1),
        (1000, 4, 100, 0),
        (10**18, 4, 100, 0),
    ],
)
def test_passive_levels_boundaries_negative_and_top(points, number, progress, remaining):
    value = level_for(points)
    assert value["number"] == number and value["progress"] == progress
    assert value["remaining"] == remaining and value["title"] == texts.LEVEL_TITLES[number - 1]
    assert LEVEL_THRESHOLDS == (0, 50, 200, 1000)
    assert (value["next_threshold"] is None) == (number == 4)


def test_men_shows_escaped_name_and_passive_level_without_changing_stats():
    value = texts.my_stats("<Ali>", 200, 3, 1)
    assert "&lt;Ali&gt;" in value and "Jami: 200 ball" in value
    assert texts.level_label(level_for(200)) in value


def test_avatar_projection_strips_metadata_before_api_bytes():
    stream, info = BytesIO(), PngImagePlugin.PngInfo()
    info.add_text("private", "metadata")
    Image.new("RGB", (64, 64)).save(stream, "PNG", pnginfo=info)
    with Image.open(BytesIO(thumbnail(stream.getvalue()))) as image:
        assert image.size == (128, 128) and "private" not in image.info


async def test_profile_gallery_countdown_and_season_leaderboard_use_correct_total(
    game_app, sessions
):
    _, _, runtime = game_app
    now = datetime(2026, 11, 13, tzinfo=UTC)
    async with sessions.begin() as session:
        session.add(Chat(id=-2, title="Other", is_active=True, bot_is_admin=True))
        await session.flush()
        session.add_all(
            [
                PointEvent(
                    chat_id=-1,
                    user_id=1,
                    delta=100,
                    reason="old",
                    created_at=datetime(2026, 10, 1, tzinfo=UTC),
                ),
                PointEvent(chat_id=-1, user_id=1, delta=20, reason="current", created_at=now),
                PointEvent(chat_id=-2, user_id=1, delta=1000, reason="other", created_at=now),
                Achievement(chat_id=-1, user_id=1, key="first_video", unlocked_at=now),
                Achievement(chat_id=-2, user_id=1, key="first_video", unlocked_at=now),
            ]
        )
    identity = SimpleNamespace(user_id=1, first_name="Ali", username=None)
    before = None
    async with sessions() as session:
        before = await session.scalar(select(func.count()).select_from(PointEvent))
    with patch("bot.services.webapp_data.utc_now", return_value=now):
        private = await profile(sessions, identity)
        chat = await runtime.groups.get(-1)
        season = await leaderboard(runtime, chat, "season")
        gallery = await achievements(sessions, chat, 1)
    assert private["points"] == 1120 and private["level"]["number"] == 4
    assert private["achievements"] == 1
    assert len(private["gallery"]) == len(texts.ACHIEVEMENTS)
    assert sum(bool(item["unlocked_at"]) for item in private["gallery"]) == 1
    assert season["items"][0]["points"] == 20
    assert season["items"][0]["level"] == level_for(120)
    assert gallery["season_ends_at"] == "2026-11-30T19:00:00+00:00"
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == before


async def test_card_level_comes_from_all_time_group_ledger_not_earned_result(game_app):
    _, _, runtime = game_app
    await runtime.points.award(-1, 1, 200, "test", "level")
    runtime.cards.enabled = True
    with patch("bot.services.result_cards.render_card", return_value=b"PNG") as render:
        await runtime.cards.ranked("Duel", [(1, "Ali", 2)], kind="duel", chat_id=-1)
    assert render.call_args.kwargs["levels"] == [texts.level_label(level_for(200))]
    assert (await runtime.points.stats(-1, 1))[0] == 200


async def test_api_avatar_backlog_is_bounded_and_optional_budget_does_not_hold_response():
    async def photos(**kwargs):
        await asyncio.Event().wait()

    cache = Avatars(SimpleNamespace(get_user_profile_photos=photos), None)
    callers = [asyncio.create_task(cache.get(user)) for user in range(1, 65)]
    try:
        await asyncio.sleep(0)  # Start each caller up to its first shielded fetch.
        assert await asyncio.wait_for(cache.get(65), 1) is None
        assert len(cache.pending) == 64
        assert await asyncio.wait_for(cache.encoded(1), 3) is None
    finally:
        for caller in callers:
            caller.cancel()
        await cache.close()
        await asyncio.gather(*callers, return_exceptions=True)
