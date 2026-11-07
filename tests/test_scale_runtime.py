from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.types import Update
from aiohttp import ClientSession, web
from pydantic import SecretStr, ValidationError

from bot.__main__ import create_dispatcher
from bot.config import Settings
from bot.services.runtime import ScaleMiddleware, ScaleRuntime
from bot.services.webhook import create_webhook_app


def config_values():
    return {
        "_env_file": None,
        "bot_token": "123456789:local_test_token",
        "bot_username": "OqibatBot",
        "instagram_handle": "oqibat",
        "owner_id": 1,
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "production"},
        {"db_pool_size": 9},
        {"db_pool_size": 21},
        {"use_webhook": True},
        {"use_webhook": True, "webhook_url": "http://example.com/hook", "webhook_secret": "test"},
        {
            "use_webhook": True,
            "webhook_url": "https://example.com/hook",
            "webhook_secret": "bad secret",
        },
    ],
)
def test_rejects_invalid_production_or_webhook_settings(overrides):
    with pytest.raises(ValidationError):
        Settings(**(config_values() | overrides))


async def test_postgres_pool_is_bounded_without_connecting():
    from bot.db.session import create_engine

    settings = Settings(
        **(
            config_values()
            | {
                "environment": "production",
                "database_url": "postgresql+asyncpg://test:fake@localhost/test",
            }
        )
    )
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_size=settings.db_pool_size
    )
    try:
        assert engine.pool.size() == 15
        assert engine.pool._max_overflow == 0
    finally:
        await engine.dispose()


async def test_message_middleware_uses_memory_only_and_membership_refresh(sessions):
    bot = SimpleNamespace(get_chat_administrators=AsyncMock(return_value=[]))
    runtime = ScaleRuntime(sessions, bot)
    middleware = ScaleMiddleware(runtime)
    message = Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1794024000,
                "chat": {"id": -1, "type": "group"},
                "from": {"id": 42, "is_bot": False, "first_name": "Sinov"},
                "text": "Salom",
            },
        }
    )
    runtime.pending.add(1, -1, 42)
    data = {}
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=AssertionError("SQL")):
        await middleware(AsyncMock(), message, data)
    assert data["has_pending_challenge"] is True
    assert runtime.metrics.updates_per_minute == 1
    membership = Update.model_validate(
        {
            "update_id": 2,
            "my_chat_member": {
                "chat": {"id": -1, "type": "group"},
                "date": 1794024000,
                "from": {"id": 42, "is_bot": False, "first_name": "Sinov"},
                "old_chat_member": {
                    "status": "left",
                    "user": {"id": 9, "is_bot": True, "first_name": "Bot"},
                },
                "new_chat_member": {
                    "status": "member",
                    "user": {"id": 9, "is_bot": True, "first_name": "Bot"},
                },
            },
        }
    )
    await middleware(AsyncMock(), membership, {})
    bot.get_chat_administrators.assert_awaited_once_with(-1)
    await runtime.sender.close()


async def test_webhook_rejects_missing_wrong_secret_and_accepts_valid_update(settings):
    settings = settings.model_copy(
        update={
            "use_webhook": True,
            "webhook_url": "https://example.com/telegram",
            "webhook_secret": SecretStr("local-secret"),
        }
    )
    dispatcher = create_dispatcher()
    bot = Bot(settings.bot_token.get_secret_value())
    app = create_webhook_app(dispatcher, bot, settings, {})
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1794024000,
            "chat": {"id": -1, "type": "group"},
            "from": {"id": 42, "is_bot": False, "first_name": "Sinov"},
            "text": "Salom",
        },
    }
    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = runner.addresses[0][1]
        async with ClientSession() as session:
            for header in ({}, {"X-Telegram-Bot-Api-Secret-Token": "wrong"}):
                async with session.post(
                    f"http://127.0.0.1:{port}/telegram", json=payload, headers=header
                ) as response:
                    assert response.status == 401
            async with session.post(
                f"http://127.0.0.1:{port}/telegram",
                json=payload,
                headers={"X-Telegram-Bot-Api-Secret-Token": "local-secret"},
            ) as response:
                assert response.status == 200
    finally:
        await runner.cleanup()
        await bot.session.close()


async def test_runtime_shutdown_flushes_and_stops_tasks(sessions):
    runtime = ScaleRuntime(sessions, SimpleNamespace())
    async with runtime:
        runtime.activity.mark_private(42, "Sinov", None)
        assert len(runtime.tasks) == 4
    assert all(task.done() for task in runtime.tasks)
    assert not runtime.activity.users
