from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot import texts
from bot.services.seasons import month_bounds
from bot.utils.time import utc_now


async def mine(message: Message, bot: Bot, points, checkins, sender) -> None:
    if message.from_user is None:
        return
    await checkins.flush()
    total, done, missed = await points.stats(message.chat.id, message.from_user.id)
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id, texts.my_stats(message.from_user.first_name, total, done, missed)
        ),
    )


async def top(message: Message, bot: Bot, points, groups, checkins, sender) -> None:
    await checkins.flush()
    chat = await groups.get(message.chat.id)
    since, until = month_bounds(utc_now(), chat.tz if chat else "Asia/Tashkent")
    weekly = await points.top(message.chat.id, since, until)
    overall = await points.top(message.chat.id)
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(message.chat.id, texts.leaderboard(weekly, overall)),
    )


async def achievements_command(message, bot, sender, achievements, checkins):
    await checkins.flush()
    rows = await achievements.list(message.chat.id, message.from_user.id, reconcile=True)
    await sender.send(
        message.chat.id, lambda: bot.send_message(message.chat.id, texts.achievement_list(rows))
    )


def create_router() -> Router:
    router = Router(name="stats")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.message.register(mine, Command("men"))
    router.message.register(top, Command("top"))
    router.message.register(achievements_command, Command("yutuqlar"))
    return router
