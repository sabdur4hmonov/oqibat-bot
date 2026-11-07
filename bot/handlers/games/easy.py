from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message, PollAnswer

from bot.services.sender import Priority
from bot.utils.admin import is_anonymous_admin

KINDS = {"duel": "duel", "viktorina": "quiz", "tanla": "wyr"}


async def start(message: Message, command: CommandObject, easy_games, bot, sender):
    error = await easy_games.start(message, KINDS[command.command])
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query: CallbackQuery, easy_games, bot, sender):
    error = await easy_games.callback(query)
    await sender.answer_callback_query(bot, query.id, text=error, show_alert=bool(error))


async def poll_answer(event: PollAnswer, easy_games):
    await easy_games.answer(event)


async def stop(message: Message, game_hub, bot, sender):
    if message.from_user is None and not is_anonymous_admin(message):
        return
    error = await game_hub.stop(
        message.chat.id,
        message.from_user.id if message.from_user else 0,
        message.reply_to_message.message_id if message.reply_to_message else None,
        anonymous_admin=is_anonymous_admin(message),
    )
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


def create_router():
    router = Router(name="easy_games")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.message.register(start, Command(*KINDS))
    router.message.register(stop, Command("stop"))
    router.callback_query.register(button, F.data.regexp(r"^d[ag]:"))
    router.poll_answer.register(poll_answer)
    return router
