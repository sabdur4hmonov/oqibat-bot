import asyncio
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import SendPhoto
from PIL import Image, ImageDraw, ImageFont
from test_easy_games import game_app as game_app
from test_game_hub_ui import button
from test_result_cards import finished_duel, photo_transport

from bot import texts
from bot.db.models import ScheduledPost
from bot.keyboards.cards import story_keyboard
from bot.services.avatars import MAX_AVATAR_BYTES, AvatarBytes, Avatars
from bot.services.cards import FONT, SIZE, STORY_SIZE, avatar, render_card


@pytest.mark.parametrize("kind", [*texts.GAME_STYLE, "weekly", "season"])
@pytest.mark.parametrize("story", [False, True])
def test_every_card_type_dimensions_and_no_missing_glyph_text(kind, story):
    original, drawn = ImageDraw.ImageDraw.text, []
    face = ImageFont.truetype(str(FONT), 32)
    missing = bytes(face.getmask("\u0378"))

    def checked(draw, xy, value, *args, **kwargs):
        assert all(bytes(face.getmask(char)) != missing for char in str(value)), value
        drawn.append(value)
        return original(draw, xy, value, *args, **kwargs)

    title = texts.GAME_EMOJIS.get(kind, "🏆") + " Oʻyin natijasi"
    with patch.object(ImageDraw.ImageDraw, "text", checked):
        result = render_card(
            title, [("Oʻtkir 😀 \u0378 <&>", 15)], "oqibat.test", kind=kind, story=story
        )
    with Image.open(BytesIO(result)) as image:
        assert image.size == (STORY_SIZE if story else SIZE)
    assert any("oqibat.test" in value for value in drawn)
    assert any("Oʻtkir" in value for value in drawn)


def png():
    data = BytesIO()
    Image.new("RGB", (64, 64), "red").save(data, "PNG")
    return data.getvalue()


def test_avatar_download_is_bounded_before_buffering_not_by_rewound_cursor():
    stream = AvatarBytes()
    stream.write(b"x" * MAX_AVATAR_BYTES)
    with pytest.raises(ValueError):
        stream.write(b"x")
    stream.seek(0)  # aiogram.download defaults to rewinding the output.
    assert stream.getbuffer().nbytes == MAX_AVATAR_BYTES


def test_avatar_is_circle_and_corrupt_photo_falls_back():
    image = Image.new("RGB", (120, 120), "blue")
    draw = ImageDraw.Draw(image)
    avatar(image, draw, "Ali Vali", png(), 10, 10, 80, "gold")
    assert image.getpixel((10, 10)) == (0, 0, 255)
    assert image.getpixel((50, 50)) == (255, 0, 0)
    avatar(image, draw, "Gʻani", b"corrupt", 10, 10, 80, "gold")
    assert image.getpixel((50, 20)) == (255, 215, 0)


async def test_avatar_cache_coalesces_users_keys_by_file_id_ttl_and_erasure():
    now = [0]
    photo = SimpleNamespace(file_id="same-file", file_size=100)
    bot = SimpleNamespace(
        get_user_profile_photos=AsyncMock(return_value=SimpleNamespace(photos=[[photo]])),
        download=AsyncMock(),
    )

    async def download(file, destination, **kwargs):
        destination.write(png())

    bot.download.side_effect = download
    cache = Avatars(bot, None, clock=lambda: now[0])
    results = await asyncio.gather(*(cache.get(1) for _ in range(10)))
    assert results[0] and results == [results[0]] * 10
    assert bot.get_user_profile_photos.await_count == bot.download.await_count == 1
    assert await cache.get(2) == results[0]
    assert bot.download.await_count == 1 and "same-file" in cache.files
    now[0] = 601
    assert await cache.get(1) == results[0]
    assert bot.get_user_profile_photos.await_count == 3
    cache.forget(1)
    assert await cache.get(1) is None and "same-file" not in cache.files
    cache.allow(1)
    bot.get_user_profile_photos.side_effect = RuntimeError("private URL must not be logged")
    assert await cache.get(1) is None
    await cache.close()


async def test_cancelled_avatar_caller_does_not_retain_completed_fetch():
    entered, release = asyncio.Event(), asyncio.Event()

    async def photos(**kwargs):
        entered.set()
        await release.wait()
        return SimpleNamespace(photos=[])

    cache = Avatars(SimpleNamespace(get_user_profile_photos=photos), None)
    caller = asyncio.create_task(cache.get(1))
    await entered.wait()
    fetch = cache.pending[1]
    caller.cancel()
    await asyncio.gather(caller, return_exceptions=True)
    release.set()
    await fetch
    await asyncio.sleep(0)
    assert not cache.pending
    await cache.close()


async def test_story_only_on_click_private_correct_size_and_duplicate_throttle(game_app, sessions):
    _, transport, runtime = game_app
    runtime.cards.enabled = True
    game = await finished_duel(runtime, sessions)
    with patch.object(transport, "make_request", side_effect=photo_transport(transport)):
        await runtime.cards.game(game)
        photos = [method for method in transport.methods if isinstance(method, SendPhoto)]
        assert len(photos) == 1
        query = button(
            runtime, f"sc:g:{game.id}", 1, story_keyboard(f"g:{game.id}"), message_id=777
        )
        await runtime.stories.callback(query)
        await runtime.stories.callback(query)
        await runtime.effects.drain()
    photos = [method for method in transport.methods if isinstance(method, SendPhoto)]
    assert len(photos) == 2 and photos[-1].chat_id == 1
    assert Image.open(BytesIO(photos[0].photo.data)).size == SIZE
    assert Image.open(BytesIO(photos[1].photo.data)).size == STORY_SIZE
    assert "oqibat.test" in photos[-1].caption


async def test_story_erasure_during_render_and_foreign_source_fail_closed(game_app, sessions):
    _, transport, runtime = game_app
    runtime.cards.enabled = True
    game = await finished_duel(runtime, sessions)
    with patch.object(transport, "make_request", side_effect=photo_transport(transport)):
        await runtime.cards.game(game)
        query = button(
            runtime, f"sc:g:{game.id}", 1, story_keyboard(f"g:{game.id}"), message_id=778
        )
        assert await runtime.stories.source(query) is None
        query = query.model_copy(
            update={"message": query.message.model_copy(update={"message_id": 777})}
        )
        entered, release = asyncio.Event(), asyncio.Event()

        async def render(*args, **kwargs):
            entered.set()
            await release.wait()
            return png()

        with patch.object(runtime.cards, "ranked", side_effect=render):
            await runtime.stories.callback(query)
            await asyncio.wait_for(entered.wait(), 2)
            assert await runtime.owner_tools.erase(1, runtime.owner_tools.confirm(1))
            release.set()
            await runtime.effects.drain()
    assert len([method for method in transport.methods if isinstance(method, SendPhoto)]) == 1
    assert await runtime.stories.source(query) is None


@pytest.mark.parametrize("kind,prefix", [("weekly", "w"), ("season", "s")])
async def test_post_stories_validate_origin_source_and_never_write_points(
    game_app, sessions, kind, prefix
):
    from sqlalchemy import func, select

    from bot.db.models import PointEvent
    from bot.utils.time import utc_now

    _, _, runtime = game_app
    day = date(2026, 11, 1)
    async with sessions.begin() as session:
        session.add(
            ScheduledPost(
                chat_id=-1,
                kind=kind,
                local_date=day,
                status="sent",
                sent_at=utc_now(),
                origin_chat_id=-1,
                message_id=777,
            )
        )
    source = f"{prefix}:-1:{day}"
    query = button(runtime, f"sc:{source}", 1, story_keyboard(source), message_id=777)
    assert (await runtime.stories.source(query))[3] == kind
    async with sessions.begin() as session:
        post = await session.get(ScheduledPost, (-1, kind, day))
        post.origin_chat_id = -99
        before = await session.scalar(select(func.count()).select_from(PointEvent))
    assert await runtime.stories.source(query) is None
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PointEvent)) == before
