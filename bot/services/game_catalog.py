"""Hub adapter. Never bypass a typed command's existing service checks."""

from aiogram.types import Message

from bot import texts
from bot.keyboards.hub import hub_keyboard
from bot.services.sender import Priority


def trusted_button(query, bot):
    message = query.message
    return bool(
        isinstance(message, Message)
        and message.from_user
        and message.from_user.id == bot.id
        and not query.from_user.is_bot
        and message.reply_markup
        and any(
            button.callback_data == query.data
            for row in message.reply_markup.inline_keyboard
            for button in row
        )
    )


class GameCatalog:
    def __init__(self, runtime, bot):
        self.runtime, self.bot, self.sender = runtime, bot, runtime.sender

    async def show(self, message):
        await self.sender.send(
            message.chat.id,
            lambda: self.bot.send_message(
                message.chat.id, texts.HUB_INTRO, reply_markup=hub_keyboard()
            ),
            priority=Priority.GAME,
        )

    async def callback(self, query):
        if not trusted_button(query, self.bot) or (
            self.runtime.locks.resolve(query.message.chat.id) != query.message.chat.id
        ):
            await self.sender.answer_callback_query(
                self.bot, query.id, text=texts.GAME_BUTTON_EXPIRED, show_alert=True
            )
            return
        operation, _, value = (query.data or "").partition(":")
        if operation == "hc" and value in {"home", *texts.HUB_CATEGORIES}:
            await self.sender.answer_callback_query(self.bot, query.id)
            await self.sender.send(
                query.message.chat.id,
                lambda: self.bot.edit_message_text(
                    texts.HUB_INTRO,
                    chat_id=query.message.chat.id,
                    message_id=query.message.message_id,
                    reply_markup=hub_keyboard(value),
                ),
                priority=Priority.GAME,
            )
            return
        if operation != "hg" or value not in texts.GAME_STYLE:
            return
        if query.message.chat.type not in {"group", "supergroup"}:
            await self.sender.answer_callback_query(
                self.bot, query.id, text=texts.HUB_GROUP_ONLY, show_alert=True
            )
            return
        await self.sender.answer_callback_query(self.bot, query.id)
        # The menu's author is the bot; the actor must be the clicking human.
        message = query.message.model_copy(
            update={
                "from_user": query.from_user,
                "sender_chat": None,
                "reply_to_message": None,
                "text": None,
            }
        )
        runtime = self.runtime
        if value in {"duel", "quiz", "wyr"}:
            error = await runtime.easy_games.start(message, value)
        elif value in {"number", "math"}:
            error = await runtime.quick_games.start(message, value)
        elif value in {"secret", "kim", "telephone", "memory"}:
            error = await runtime.private_games.start(message, value)
        else:
            service = {
                "rps": runtime.rps_game,
                "krokodil": runtime.krokodil_game,
                "hyj": runtime.truth_dare,
                "mafia": runtime.mafia_game,
            }[value]
            error = await service.start(message)
        if error:
            await self.sender.send(
                message.chat.id,
                lambda: self.bot.send_message(message.chat.id, error),
                priority=Priority.GAME,
            )
