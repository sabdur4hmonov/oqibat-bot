from aiogram import F, Router
from aiogram.filters import Command, CommandObject

from bot import texts
from bot.services.sender import Priority

KINDS = {"sontop": "number", "matematika": "math"}


async def start(message, command: CommandObject, quick_games, bot, sender):
    error = await quick_games.start(message, KINDS[command.command])
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query, quick_games, bot, sender):
    result = await quick_games.callback(query)
    await sender.answer_callback_query(bot, query.id, text=result, show_alert=True)


async def catalog(message, bot, sender):
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(message.chat.id, texts.GAME_CATALOG),
        priority=Priority.GAME,
    )


def create_router():
    router = Router(name="quick_games")
    router.message.register(
        catalog, Command("oyinlar"), F.chat.type.in_({"private", "group", "supergroup"})
    )
    router.message.register(start, Command(*KINDS), F.chat.type.in_({"group", "supergroup"}))
    router.callback_query.register(button, F.data.startswith("qm:"))
    return router
