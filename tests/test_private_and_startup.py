import os
import subprocess
import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import DeleteWebhook, GetMe, SendMessage, SetMyCommands
from aiogram.types import Message, Update, User
from pydantic import SecretStr

from bot import texts
from bot.__main__ import ALLOWED_UPDATES, create_dispatcher, run
from bot.db.models import Membership
from bot.db.models import User as DbUser
from bot.services.activity import ActivityBuffer
from bot.services.sender import Sender

TOKEN = "123456789:local_test_token_never_used_on_telegram"


class LocalTelegram(BaseSession):
    """Real aiogram serialization/routing with no Telegram requests."""

    def __init__(self):
        super().__init__()
        self.methods = []
        self.closed = False

    async def close(self):
        self.closed = True

    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109 - aiogram interface
        self.methods.append(method)
        if isinstance(method, GetMe):
            return User(id=123456789, is_bot=True, first_name="Oqibat", username="OqibatBot")
        if isinstance(method, (SetMyCommands, DeleteWebhook)):
            return True
        if isinstance(method, SendMessage):
            return Message(
                message_id=100,
                date=datetime.now(UTC),
                chat={"id": method.chat_id, "type": "private"},
                text=method.text,
            )
        raise AssertionError(f"Unexpected Telegram method: {type(method).__name__}")

    async def stream_content(self, *args, **kwargs):
        if False:
            yield b""


def update_for(command, chat_type="private"):
    return Update.model_validate(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1794024000,
                "chat": {"id": 42 if chat_type == "private" else -42, "type": chat_type},
                "from": {"id": 42, "is_bot": False, "first_name": "<b>Sardor & do‘st</b>"},
                "text": command,
                "entities": [{"type": "bot_command", "offset": 0, "length": len(command)}],
            },
        }
    )


@pytest.mark.parametrize("command", ["/start", "/help"])
async def test_private_command_uzbek_footer_button_and_no_opt_in(sessions, settings, command):
    transport = LocalTelegram()
    activity = ActivityBuffer(sessions)
    async with Bot(
        TOKEN, session=transport, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    ) as bot:
        await create_dispatcher().feed_update(
            bot,
            update_for(command),
            settings=settings,
            sessions=sessions,
            sender=Sender(sessions),
            activity=activity,
        )
    sends = [method for method in transport.methods if isinstance(method, SendMessage)]
    assert len(sends) == 1
    sent = sends[0]
    assert texts.SLOGAN in sent.text
    assert "Muallif: @oqibat.test" in sent.text
    if command == "/start":
        assert "&lt;b&gt;Sardor &amp; do‘st&lt;/b&gt;" in sent.text
    button = sent.reply_markup.inline_keyboard[0][0]
    assert button.text == texts.ADD_TO_GROUP
    assert button.url == (
        "https://t.me/OqibatBot?startgroup=add&admin=restrict_members+delete_messages+pin_messages"
    )
    await activity.flush()
    async with sessions() as session:
        assert (await session.get(DbUser, 42)).started_private is True
        assert await session.get(Membership, (-42, 42)) is None


async def test_private_start_does_not_handle_group_messages(sessions, settings):
    transport = LocalTelegram()
    async with Bot(TOKEN, session=transport) as bot:
        await create_dispatcher().feed_update(
            bot,
            update_for("/start", "group"),
            settings=settings,
            sessions=sessions,
            sender=Sender(sessions),
        )
    assert transport.methods == []


async def test_global_handler_contains_exception(sessions, settings, caplog):
    transport = LocalTelegram()
    with patch.object(ActivityBuffer, "mark_private", side_effect=RuntimeError("buffer failure")):
        async with Bot(TOKEN, session=transport) as bot:
            await create_dispatcher().feed_update(
                bot,
                update_for("/start"),
                settings=settings,
                sessions=sessions,
                sender=Sender(sessions),
                activity=ActivityBuffer(sessions),
            )
    assert "Unhandled error processing update 1" in caplog.text


async def test_bootstrap_registers_scopes_and_required_updates(database_url, settings):
    transport = LocalTelegram()
    config = settings.model_copy(update={"database_url": SecretStr(database_url)})

    def bot_factory(**kwargs):
        assert kwargs["default"].parse_mode == ParseMode.HTML
        return Bot(session=transport, **kwargs)

    with (
        patch("bot.__main__.Bot", side_effect=bot_factory),
        patch("bot.__main__.Dispatcher.start_polling", new_callable=AsyncMock) as polling,
    ):
        await run(config)
    registrations = [m for m in transport.methods if isinstance(m, SetMyCommands)]
    assert [r.scope.type for r in registrations] == ["all_private_chats", "all_group_chats"]
    assert [c.command for c in registrations[0].commands] == [
        "start",
        "help",
        "oyinlar",
        "stats",
        "maxfiylik",
        "malumotlarimni_ochir",
    ]
    assert {command.command for command in registrations[1].commands} == set(texts.GROUP_MENU)
    assert polling.await_args.kwargs["allowed_updates"] == ALLOWED_UPDATES
    assert set(ALLOWED_UPDATES) == {
        "message",
        "callback_query",
        "my_chat_member",
        "chat_member",
        "poll_answer",
    }
    assert transport.closed


async def test_username_mismatch_prevents_polling(database_url, settings):
    transport = LocalTelegram()
    config = settings.model_copy(
        update={"database_url": SecretStr(database_url), "bot_username": "OtherBot"}
    )
    with (
        patch("bot.__main__.Bot", side_effect=lambda **kwargs: Bot(session=transport, **kwargs)),
        patch("bot.__main__.Dispatcher.start_polling", new_callable=AsyncMock) as polling,
        pytest.raises(RuntimeError, match="BOT_USERNAME"),
    ):
        await run(config)
    polling.assert_not_awaited()
    assert transport.closed


def test_python_module_check_starts_without_network(database_url):
    env = os.environ | {
        "PYTHONIOENCODING": "utf-8",
        "DATABASE_URL": database_url,
        "BOT_TOKEN": TOKEN,
        "BOT_USERNAME": "OqibatBot",
        "INSTAGRAM_HANDLE": "oqibat.test",
        "OWNER_ID": "123",
    }
    result = subprocess.run(
        [sys.executable, "-m", "bot", "--check"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Telegram aloqasi tekshirilmadi" in result.stdout
    assert TOKEN not in result.stdout + result.stderr


def test_missing_token_has_clean_config_error(monkeypatch):
    env = {key: value for key, value in os.environ.items() if key != "BOT_TOKEN"}
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-m", "bot"],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    assert "Sozlamalarda xato" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
