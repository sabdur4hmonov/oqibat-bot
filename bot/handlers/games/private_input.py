from aiogram import F, Router
from aiogram.filters import Command, CommandObject

from bot import texts
from bot.services.sender import Priority


async def start(message, private_games, sender, bot, command: CommandObject):
    kind = {"yashirin": "secret", "kimaytdi": "kim"}[command.command]
    error = await private_games.start(message, kind)
    if error:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, error),
            priority=Priority.GAME,
        )


async def accuse(message, private_games, sender, bot):
    result = await private_games.accuse(message)
    if result:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, result),
            priority=Priority.GAME,
        )


async def button(query, private_games, sender, bot):
    result = await private_games.callback(query)
    await sender.answer_callback_query(bot, query.id, text=result, show_alert=True)


async def hide(query, private_games, sender, bot):
    await sender.answer_callback_query(bot, query.id, text=texts.PRIVATE_GAME_HIDE_WAIT)

    async def perform():
        result = await private_games.hide(query)
        await sender.send(
            query.from_user.id,
            lambda: bot.send_message(query.from_user.id, result),
            priority=Priority.GAME,
        )

    private_games.hub.effects.start(perform())


async def private(message, private_contexts, private_games, sender, bot):
    if not message.from_user or message.from_user.is_bot:
        return
    game = private_contexts.get(message.from_user.id)
    if not game:
        return
    result = (
        texts.PRIVATE_GAME_MAFIA_INPUT
        if game.game == "mafia"
        else await private_games.private_input(game, message)
    )
    if result:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(message.chat.id, result),
            priority=Priority.GAME,
        )


def create_router():
    router = Router(name="private_input_games")
    router.message.register(
        start, F.chat.type.in_({"group", "supergroup"}), Command("yashirin", "kimaytdi")
    )
    router.message.register(accuse, F.chat.type.in_({"group", "supergroup"}), Command("fosh"))
    router.callback_query.register(button, F.data.startswith("pg:"))
    router.callback_query.register(hide, F.data.startswith("ph:"))
    router.message.register(private, F.chat.type == "private", ~F.text.startswith("/"))
    return router
