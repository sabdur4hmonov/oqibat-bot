from aiogram import F, Router
from aiogram.filters import Command

from bot.services.sender import Priority


async def start(message, rps_game, bot, sender):
    error = await rps_game.start(message)
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query, rps_game, bot, sender):
    result = await rps_game.callback(query)
    await sender.answer_callback_query(bot, query.id, text=result, show_alert=True)


def create_router():
    router = Router(name="rps")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.message.register(start, Command("tqq", "toshqaychiqogoz"))
    router.callback_query.register(button, F.data.startswith("rp:"))
    return router
