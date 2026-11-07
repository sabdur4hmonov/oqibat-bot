from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.services.sender import Priority


async def start(message: Message, truth_dare, bot, sender):
    error = await truth_dare.start(message)
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def button(query: CallbackQuery, truth_dare, sender, bot):
    error = await truth_dare.callback(query)
    await sender.answer_callback_query(bot, query.id, text=error, show_alert=bool(error))


def create_router():
    router = Router(name="truth_dare")
    router.message.register(start, F.chat.type.in_({"group", "supergroup"}), Command("hyj"))
    router.callback_query.register(button, F.data.regexp(r"^h[tdr]:"))
    return router
