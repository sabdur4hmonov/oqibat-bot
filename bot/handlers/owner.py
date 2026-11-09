"""Thin private owner/privacy commands; confirmation always belongs to its requester."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts


async def privacy(message, bot, sender):
    await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, texts.PRIVACY))


async def stats(message, bot, sender, owner_tools, activity):
    if message.from_user.id != owner_tools.owner_id:
        content = texts.OWNER_ONLY
    else:
        await activity.flush()
        content = texts.owner_stats(await owner_tools.stats())
    await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, content))


async def erase_request(message, bot, sender, owner_tools):
    token = owner_tools.confirm(message.from_user.id)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=texts.ERASE_CONFIRM, callback_data=f"erase:{token}")]
        ]
    )
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(message.chat.id, texts.ERASE_WARNING, reply_markup=keyboard),
    )


async def erase_confirm(callback, bot, sender, owner_tools):
    if (
        not callback.message
        or callback.message.chat.type != "private"
        or callback.message.chat.id != callback.from_user.id
    ):
        await sender.answer_callback_query(
            bot, callback.id, text=texts.ERASE_EXPIRED, show_alert=True
        )
        return
    # Answer immediately before potentially expensive deletion and buffer/lock coordination.
    await sender.answer_callback_query(bot, callback.id, text=texts.ERASE_WORKING)
    success = await owner_tools.erase(callback.from_user.id, callback.data.removeprefix("erase:"))
    await sender.send(
        callback.from_user.id,
        lambda: bot.edit_message_text(
            texts.ERASE_DONE if success else texts.ERASE_EXPIRED,
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            reply_markup=None,
        ),
    )


def create_router():
    router = Router(name="owner_privacy")
    router.message.register(privacy, Command("maxfiylik"))
    router.message.register(stats, F.chat.type == "private", Command("stats"))
    router.message.register(
        erase_request, F.chat.type == "private", Command("malumotlarimni_ochir")
    )
    router.callback_query.register(erase_confirm, F.data.startswith("erase:"))
    return router
