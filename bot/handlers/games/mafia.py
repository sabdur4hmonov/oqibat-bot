from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.services.sender import Priority


async def start(message: Message, mafia_game, bot, sender):
    error = await mafia_game.start(message)
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query: CallbackQuery, mafia_game, bot, sender):
    result = await mafia_game.callback(query)
    await sender.answer_callback_query(bot, query.id, text=result, show_alert=True)


def create_router():
    router = Router(name="mafia")
    router.message.register(start, F.chat.type.in_({"group", "supergroup"}), Command("mafia"))
    router.callback_query.register(button, F.data.startswith("mf:"))
    return router
