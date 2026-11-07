from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.services.sender import Priority


async def start(message: Message, krokodil_game, bot, sender):
    error = await krokodil_game.start(message)
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query: CallbackQuery, krokodil_game, sender, bot):
    answer = await krokodil_game.callback(query)
    await sender.answer_callback_query(bot, query.id, text=answer, show_alert=True)


def create_router():
    router = Router(name="krokodil")
    router.message.register(start, F.chat.type.in_({"group", "supergroup"}), Command("krokodil"))
    router.callback_query.register(button, F.data.regexp(r"^k[ws]:"))
    return router
