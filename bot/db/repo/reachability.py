"""Persist blocked private chats or groups that removed the bot."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.models import Chat, User


async def mark_inactive(sessions: async_sessionmaker, chat_id: int) -> None:
    async with sessions.begin() as session:
        if chat_id > 0:
            await session.execute(
                update(User).where(User.id == chat_id).values(started_private=False)
            )
        else:
            await session.execute(update(Chat).where(Chat.id == chat_id).values(is_active=False))
