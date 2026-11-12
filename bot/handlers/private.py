from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from bot import texts
from bot.config import Settings
from bot.games.private_input import PREFIXES, parse_payload
from bot.keyboards.private import private_keyboard
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
    private_games=None,
) -> None:
    if message.from_user is None:
        return
    activity.mark_private(
        message.from_user.id, message.from_user.first_name, message.from_user.username
    )
    if command.args and any(command.args.startswith(prefix + "_") for prefix in PREFIXES.values()):
        await activity.flush()
        parsed = parse_payload(command.args)
        result = (
            texts.MAFIA_LOBBY_CLOSED
            if command.args.startswith("mafia_")
            else texts.PRIVATE_GAME_CLOSED
        )
        if parsed:
            kind, game_id = parsed
            if kind == "mafia" and mafia_game:
                result = await mafia_game.join(game_id, message.from_user)
            elif private_games:
                result = await private_games.join(game_id, message.from_user, kind)
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
            reply_markup=private_keyboard(settings),
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
            reply_markup=private_keyboard(settings),
        ),
    )


def create_router() -> Router:
    router = Router(name="private")
    router.message.filter(F.chat.type == "private")
    router.message.register(start, CommandStart())
    router.message.register(help_command, Command("help"))
    return router
