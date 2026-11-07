"""Private-chat reachability, without opting anyone into a group."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.models import User


async def record_private_user(
    sessions: async_sessionmaker, user_id: int, first_name: str, username: str | None
) -> None:
    async with sessions.begin() as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(id=user_id)
            session.add(user)
        user.first_name = first_name
        user.username = username
        user.started_private = True
