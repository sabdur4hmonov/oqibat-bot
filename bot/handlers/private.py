from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from bot import texts
from bot.config import Settings
from bot.keyboards.private import add_to_group_keyboard
from bot.services.activity import ActivityBuffer
from bot.services.sender import Priority, Sender


async def start(
    message: Message,
    bot: Bot,
    settings: Settings,
    activity: ActivityBuffer,
    sender: Sender,
    command: CommandObject,
    mafia_game=None,
) -> None:
    if message.from_user is None:
        return
    activity.mark_private(
        message.from_user.id, message.from_user.first_name, message.from_user.username
    )
    if command.args and command.args.startswith("mafia_"):
        await activity.flush()
        value = command.args.removeprefix("mafia_")
        result = texts.MAFIA_LOBBY_CLOSED
        if mafia_game is not None and value.isascii() and value.isdecimal() and len(value) <= 19:
            result = await mafia_game.join(int(value), message.from_user)
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, result),
            priority=Priority.GAME,
        )
        return
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id,
            texts.start_text(message.from_user.first_name, settings.instagram_handle),
            reply_markup=add_to_group_keyboard(settings.bot_username),
        ),
    )


async def help_command(
    message: Message, bot: Bot, settings: Settings, activity: ActivityBuffer, sender: Sender
) -> None:
    if message.from_user is None:
        return
    activity.mark_private(
        message.from_user.id, message.from_user.first_name, message.from_user.username
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
