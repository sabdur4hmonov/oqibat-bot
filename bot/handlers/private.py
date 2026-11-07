from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot import texts
from bot.config import Settings
from bot.db.repo.users import record_private_user
from bot.keyboards.private import add_to_group_keyboard
from bot.services.sender import Sender


async def start(
    message: Message, bot: Bot, settings: Settings, sessions: async_sessionmaker, sender: Sender
) -> None:
    if message.from_user is None:
        return
    await record_private_user(
        sessions, message.from_user.id, message.from_user.first_name, message.from_user.username
    )
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id,
            texts.start_text(message.from_user.first_name, settings.instagram_handle),
            reply_markup=add_to_group_keyboard(settings.bot_username),
        ),
    )


async def help_command(
    message: Message, bot: Bot, settings: Settings, sessions: async_sessionmaker, sender: Sender
) -> None:
    if message.from_user is None:
        return
    await record_private_user(
        sessions, message.from_user.id, message.from_user.first_name, message.from_user.username
    )
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id,
            texts.help_text(settings.instagram_handle),
            reply_markup=add_to_group_keyboard(settings.bot_username),
        ),
    )


def create_router() -> Router:
    router = Router(name="private")
    router.message.filter(F.chat.type == "private")
    router.message.register(start, CommandStart())
    router.message.register(help_command, Command("help"))
    return router
