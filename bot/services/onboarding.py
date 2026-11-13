"""Three short admin steps; settings persist, navigation expires on restart."""

from collections import OrderedDict

from aiogram.types import InlineKeyboardButton

from bot import texts
from bot.keyboards.group import join_keyboard
from bot.services.game_catalog import trusted_button
from bot.services.locks import ChatLocks
from bot.services.settings import parse_setting
from bot.utils.admin import is_admin

STEPS = (
    ("daily_time", ("08:00", "09:00", "18:00", "21:00")),
    ("challenges_per_day", ("0", "1", "2", "3")),
    ("penalty_mode", ("off", "points", "mute", "kick")),
)


def setup_keyboard(step):
    keyboard = join_keyboard()
    if step < len(STEPS):
        values = STEPS[step][1]
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.SETUP_VALUES.get(value, value), callback_data=f"qs:{step}:{index}"
                )
                for index, value in enumerate(values)
            ]
        )
    keyboard.inline_keyboard.append(
        [InlineKeyboardButton(text=texts.SETUP_FULL, callback_data="settings")]
    )
    return keyboard


class QuickSetup:
    def __init__(self, runtime, bot):
        self.runtime, self.bot = runtime, bot
        self.pending = OrderedDict()
        self.locks = ChatLocks()

    def remember(self, chat_id, message_id):
        self.pending[chat_id] = (message_id, 0)
        self.pending.move_to_end(chat_id)
        if len(self.pending) > 20_000:
            self.pending.popitem(last=False)

    async def callback(self, query):
        sender = self.runtime.sender
        if not trusted_button(query, self.bot) or (
            self.runtime.locks.resolve(query.message.chat.id) != query.message.chat.id
        ):
            await sender.answer_callback_query(
                self.bot, query.id, text=texts.GAME_BUTTON_EXPIRED, show_alert=True
            )
            return
        chat_id = query.message.chat.id
        error = texts.ADMINS_ONLY
        try:
            allowed = await is_admin(self.runtime.admins, chat_id, query.from_user.id)
        except Exception:
            allowed, error = False, texts.ADMIN_CHECK_FAILED
        if not allowed:
            await sender.answer_callback_query(self.bot, query.id, text=error, show_alert=True)
            return
        await sender.answer_callback_query(self.bot, query.id)
        async with self.locks.for_chat(chat_id):
            try:
                prefix, step, choice = query.data.split(":")
                step, choice = int(step), int(choice)
                if (
                    prefix != "qs"
                    or not 0 <= step < 3
                    or choice < 0
                    or self.pending.get(chat_id) != (query.message.message_id, step)
                ):
                    raise ValueError()
                field, choices = STEPS[step]
                value = parse_setting(field, choices[choice])
            except (ValueError, IndexError):
                return
            chat = await self.runtime.groups.change_setting(chat_id, field, value)
            if chat is None:
                return
            step += 1
            self.pending[chat_id] = (query.message.message_id, step)
            await sender.send(
                chat_id,
                lambda: self.bot.edit_message_text(
                    texts.SETUP_STEPS[step] if step < 3 else texts.SETUP_DONE,
                    chat_id=chat_id,
                    message_id=query.message.message_id,
                    reply_markup=setup_keyboard(step),
                ),
            )
