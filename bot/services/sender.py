"""Single boundary for outbound Telegram sends. Failed sends return None."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.repo.reachability import mark_inactive

logger = logging.getLogger(__name__)
T = TypeVar("T")


class Sender:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def send(self, chat_id: int | None, operation: Callable[[], Awaitable[T]]) -> T | None:
        for attempt in range(2):
            try:
                return await operation()
            except TelegramRetryAfter as error:
                if attempt == 0:
                    logger.warning(
                        "Telegram rate limit; retrying after %s seconds", error.retry_after
                    )
                    await asyncio.sleep(error.retry_after)
                else:
                    logger.warning("Telegram rate limit persisted for chat %s", chat_id)
            except TelegramForbiddenError:
                logger.warning("Telegram access denied for chat %s", chat_id)
                if chat_id is not None:
                    try:
                        await mark_inactive(self.sessions, chat_id)
                    except Exception:
                        logger.exception("Could not mark chat %s inactive", chat_id)
                return None
            except Exception:
                logger.exception("Telegram operation failed for chat %s", chat_id)
                return None
        return None
