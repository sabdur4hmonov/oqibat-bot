import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

import pytest
from aiogram import Dispatcher
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import GetChatMember
from aiohttp import ClientSession, web
from pydantic import ValidationError
from sqlalchemy import func, select
from test_easy_games import game_app as game_app

from bot import texts
from bot.config import Settings
from bot.db.models import Base, PointEvent, User
from bot.keyboards.private import group_keyboard, private_keyboard
from bot.services.webapp import create_webapp_app, polling_webapp
from bot.services.webapp_auth import InitDataError, validate_init_data
from bot.services.webhook import create_webhook_app

TOKEN = "123456789:local_test_token_never_used_on_telegram"
NOW = 1800000000


def signed(*, token=TOKEN, **fields):
    values = {"auth_date": str(NOW), "user": json.dumps({"id": 2, "first_name": "<Ali>"})}
    values.update(fields)
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_init_data_hmac_all_fields_including_signature_and_age_boundaries():
    value = signed(signature="ed25519-value", start_param="-123")
    identity = validate_init_data(value, TOKEN, now=NOW)
    assert (identity.user_id, identity.first_name, identity.start_param) == (2, "<Ali>", "-123")
    validate_init_data(value, TOKEN, now=NOW + 86400)
    validate_init_data(value, TOKEN, now=NOW - 30)
    for token, raw, now in [
        (TOKEN + "wrong", value, NOW),
        (TOKEN, value.replace("ed25519-value", "tampered"), NOW),
        (TOKEN, value + "&auth_date=1800000000", NOW),
        (TOKEN, value, NOW + 86401),
        (TOKEN, value, NOW - 31),
    ]:
        with pytest.raises(InitDataError):
            validate_init_data(raw, token, now=now)


@pytest.mark.parametrize("raw", ["", "x" * 8193, "hash=00", "bad=%FF", "user=x&user=y", "x"])
def test_malformed_init_data(raw):
    with pytest.raises(InitDataError):
        validate_init_data(raw, TOKEN, now=NOW)


@pytest.mark.parametrize(
    "user", [[], None, {"id": True}, {"id": -1}, {"id": 2**63}, {"id": 2, "first_name": []}]
)
def test_authenticated_but_invalid_identity(user):
    with pytest.raises(InitDataError):
        validate_init_data(signed(user=json.dumps(user)), TOKEN, now=NOW)


@pytest.mark.parametrize(
    "status,present,allowed",
    [
        ("creator", False, True),
        ("administrator", False, True),
        ("member", False, True),
        ("restricted", True, True),
        ("restricted", False, False),
        ("left", False, False),
        ("kicked", False, False),
    ],
)
def test_live_membership_status(status, present, allowed):
    from bot.handlers.webapp import member_allowed

    assert member_allowed(SimpleNamespace(status=status, is_member=present)) is allowed


@asynccontextmanager
async def http(app):
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        async with ClientSession(base_url=f"http://127.0.0.1:{port}") as client:
            yield client
    finally:
        await runner.cleanup()


async def snapshot(sessions):
    async with sessions() as session:
        return {
            name: await session.scalar(select(func.count()).select_from(table))
            for name, table in Base.metadata.tables.items()
        }


async def test_api_signed_identity_read_only_live_group_access_and_static_security(
    game_app, sessions, settings
):
    _, _, runtime = game_app
    async with sessions.begin() as session:
        session.add(PointEvent(chat_id=-1, user_id=2, delta=10, reason="test"))
    bot = SimpleNamespace(get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")))
    before = await snapshot(sessions)
    headers = {"X-Telegram-Init-Data": signed(auth_date=str(int(time.time())), start_param="-1")}
    async with http(create_webapp_app(runtime, bot, settings)) as client:
        response = await client.get("/webapp")
        assert response.status == 200
        assert "telegram-web-app.js" in await response.text()
        assert "frame-ancestors" in response.headers["Content-Security-Policy"]
        assert response.headers["Cache-Control"] == "no-store"
        for asset in ("app.js", "style.css", "labels.js"):
            assert (await client.get("/webapp/" + asset)).status == 200
        frontend = await (await client.get("/webapp/app.js")).text()
        assert "innerHTML" not in frontend and "textContent" in frontend
        assert "themeChanged" in frontend and "themeParams" in frontend
        assert (await client.get("/webapp/.env")).status == 404
        assert (await client.get("/webapp/api/profile")).status == 401
        response = await client.get("/webapp/api/profile?user_id=1", headers=headers)
        profile = await response.json()
        assert profile["id"] == 2 and profile["points"] == 10
        assert profile["groups"][0]["id"] == -1
        response = await client.get("/webapp/api/leaderboard?chat_id=-1&scope=all", headers=headers)
        assert response.status == 200
        assert (await response.json())["items"][0]["points"] == 10
        bot.get_chat_member.assert_awaited_with(-1, 2)
        response = await client.get(
            "/webapp/api/achievements?chat_id=-1&user_id=1", headers=headers
        )
        assert response.status == 200 and len((await response.json())["items"]) == 6
        bot.get_chat_member.return_value = SimpleNamespace(status="left")
        assert (
            await client.get("/webapp/api/leaderboard?chat_id=-1", headers=headers)
        ).status == 403
        assert (
            await client.get("/webapp/api/leaderboard?chat_id=-999", headers=headers)
        ).status == 403
        assert (
            await client.get("/webapp/api/leaderboard?chat_id=1", headers=headers)
        ).status == 400
        assert (
            await client.get("/webapp/api/leaderboard?chat_id=-1&scope=bad", headers=headers)
        ).status == 400
        assert (await client.post("/webapp/api/profile", headers=headers)).status == 405
        assert (await client.get("/webapp/api/unknown", headers=headers)).status == 404
        stale = {"X-Telegram-Init-Data": signed(auth_date=str(int(time.time()) - 86401))}
        assert (await client.get("/webapp/api/profile", headers=stale)).status == 401
        unknown = {
            "X-Telegram-Init-Data": signed(
                auth_date=str(int(time.time())), user=json.dumps({"id": 99})
            )
        }
        assert (await client.get("/webapp/api/profile", headers=unknown)).status == 200
    assert await snapshot(sessions) == before
    async with sessions() as session:
        assert await session.get(User, 99) is None


async def test_api_telegram_429_pauses_sender_and_returns_bounded_error(game_app, settings):
    _, _, runtime = game_app
    bot = SimpleNamespace(
        get_chat_member=AsyncMock(
            side_effect=TelegramRetryAfter(
                method=GetChatMember(chat_id=-1, user_id=2), message="slow", retry_after=12
            )
        )
    )
    headers = {"X-Telegram-Init-Data": signed(auth_date=str(int(time.time())))}
    async with http(create_webapp_app(runtime, bot, settings)) as client:
        response = await client.get("/webapp/api/leaderboard?chat_id=-1", headers=headers)
        assert response.status == 503
        assert (await response.json())["error"] == texts.WEB_COPY["busy"]
        assert runtime.sender.limiter.global_pause == runtime.sender.clock.now() + 12
        assert (
            await client.get("/webapp/api/leaderboard?chat_id=-1", headers=headers)
        ).status == 503
        assert bot.get_chat_member.await_count == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://example.uz/webapp",
        "https://example.uz/",
        "https://u:p@example.uz/webapp",
        "https://example.uz/webapp?x=1",
    ],
)
def test_webapp_configuration_rejects_insecure_or_wrong_url(settings, url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(settings.model_dump() | {"webapp_url": url}))


async def test_optional_hosting_and_private_vs_group_buttons(game_app, settings):
    _, _, runtime = game_app
    assert len(private_keyboard(settings).inline_keyboard) == 1
    configured = Settings(
        _env_file=None, **(settings.model_dump() | {"webapp_url": "https://oqibat.example/webapp"})
    )
    private = private_keyboard(configured).inline_keyboard[-1][0]
    group = group_keyboard(configured, -100123).inline_keyboard[-1][0]
    assert private.web_app.url == configured.webapp_url and private.url is None
    assert group.web_app is None and group.url == "https://t.me/OqibatBot?startapp=-100123"
    async with polling_webapp(None, None, settings):
        pass  # Disabled mode must never construct/bind a server.
    webhook = Settings(
        _env_file=None,
        **(
            configured.model_dump()
            | {
                "use_webhook": True,
                "webhook_url": "https://oqibat.example/telegram",
                "webhook_secret": "secret",
            }
        ),
    )
    app = create_webhook_app(Dispatcher(), runtime.game_hub.bot, webhook, {"runtime": runtime})
    paths = {route.resource.canonical for route in app.router.routes()}
    assert {"/telegram", "/webapp", "/webapp/api/profile"} <= paths
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            **(webhook.model_dump() | {"webhook_url": "https://oqibat.example/webapp/api"}),
        )
