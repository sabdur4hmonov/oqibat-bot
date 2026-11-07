import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage

from bot.db.models import Chat, User
from bot.services.sender import Sender

METHOD = SendMessage(chat_id=1, text="test")


async def test_rate_limit_retries_exactly_once(sessions):
    operation = AsyncMock(
        side_effect=[TelegramRetryAfter(method=METHOD, message="wait", retry_after=2), "sent"]
    )
    with patch("bot.services.sender.asyncio.sleep", new_callable=AsyncMock) as sleep:
        assert await Sender(sessions).send(1, operation) == "sent"
    sleep.assert_awaited_once_with(2)
    assert operation.await_count == 2


async def test_second_rate_limit_does_not_escape(sessions):
    operation = AsyncMock(
        side_effect=TelegramRetryAfter(method=METHOD, message="wait", retry_after=1)
    )
    with patch("bot.services.sender.asyncio.sleep", new_callable=AsyncMock):
        assert await Sender(sessions).send(1, operation) is None
    assert operation.await_count == 2


@pytest.mark.parametrize("chat_id", [1, -1])
async def test_forbidden_marks_target_inactive(sessions, chat_id):
    async with sessions.begin() as session:
        session.add(User(id=1, first_name="Test", started_private=True))
        session.add(Chat(id=-1, title="Sinov"))
    operation = AsyncMock(side_effect=TelegramForbiddenError(method=METHOD, message="forbidden"))
    assert await Sender(sessions).send(chat_id, operation) is None
    async with sessions() as session:
        user = await session.get(User, 1)
        chat = await session.get(Chat, -1)
        assert user.started_private == (chat_id != 1)
        assert chat.is_active == (chat_id != -1)


async def test_forbidden_after_retry_marks_inactive(sessions):
    async with sessions.begin() as session:
        session.add(User(id=1, first_name="Test", started_private=True))
    operation = AsyncMock(
        side_effect=[
            TelegramRetryAfter(method=METHOD, message="wait", retry_after=1),
            TelegramForbiddenError(method=METHOD, message="blocked"),
        ]
    )
    with patch("bot.services.sender.asyncio.sleep", new_callable=AsyncMock):
        assert await Sender(sessions).send(1, operation) is None
    async with sessions() as session:
        assert (await session.get(User, 1)).started_private is False


async def test_database_failure_during_forbidden_is_contained(sessions):
    operation = AsyncMock(side_effect=TelegramForbiddenError(method=METHOD, message="blocked"))
    with patch("bot.services.sender.mark_inactive", side_effect=RuntimeError("database offline")):
        assert await Sender(sessions).send(1, operation) is None


async def test_other_errors_do_not_crash_next_send(sessions):
    sender = Sender(sessions)
    operation = AsyncMock(side_effect=TelegramBadRequest(method=METHOD, message="bad request"))
    assert await sender.send(1, operation) is None
    assert await sender.send(1, AsyncMock(return_value="next")) == "next"
    assert operation.await_count == 1


async def test_cancellation_propagates(sessions):
    with pytest.raises(asyncio.CancelledError):
        await Sender(sessions).send(1, AsyncMock(side_effect=asyncio.CancelledError))
