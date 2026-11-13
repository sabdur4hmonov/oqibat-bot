from aiogram import F, Router
from aiogram.filters import Command, CommandObject

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


async def catalog(message, game_catalog):
    await game_catalog.show(message)


async def hub_button(query, game_catalog):
    await game_catalog.callback(query)


async def story_button(query, stories):
    await stories.callback(query)


def create_router():
    router = Router(name="quick_games")
    router.message.register(
        catalog, Command("oyinlar"), F.chat.type.in_({"private", "group", "supergroup"})
    )
    router.message.register(start, Command(*KINDS), F.chat.type.in_({"group", "supergroup"}))
    router.callback_query.register(button, F.data.startswith("qm:"))
    router.callback_query.register(hub_button, F.data.startswith("hc:") | F.data.startswith("hg:"))
    router.callback_query.register(story_button, F.data.startswith("sc:"))
    return router
