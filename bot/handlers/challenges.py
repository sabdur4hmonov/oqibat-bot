from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot import texts
from bot.handlers.settings import permitted
from bot.services.challenges import KIND_ALIASES
from bot.utils.admin import is_anonymous_admin


async def force_challenge(
    message: Message, command: CommandObject, bot: Bot, admins, sender, challenge_service
) -> None:
    if message.from_user is None and not is_anonymous_admin(message):
        return
    allowed, error = await permitted(
        admins, message.chat.id, message.from_user.id if message.from_user else None, message
    )
    if not allowed:
        await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, error))
        return
    argument = (command.args or "").strip().lower()
    if argument and argument not in KIND_ALIASES:
        result = texts.CHALLENGE_ARGUMENTS
    else:
        result = await challenge_service.assign(
            message.chat.id, KIND_ALIASES.get(argument), force=True
        )
    if result:
        await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, result))


def create_router() -> Router:
    router = Router(name="challenges")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.message.register(force_challenge, Command("vazifa"))
    return router
