from aiogram import Bot, F, Router
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, ForceReply, Message

from bot import texts
from bot.keyboards.group import setting_choices, settings_keyboard
from bot.services.settings import INPUT_FIELDS, parse_setting
from bot.utils.admin import is_admin


async def permitted(admins, chat_id: int, user_id: int) -> tuple[bool, str]:
    try:
        return (
            (True, "") if await is_admin(admins, chat_id, user_id) else (False, texts.ADMINS_ONLY)
        )
    except Exception:
        return False, texts.ADMIN_CHECK_FAILED


async def settings(message: Message, bot: Bot, groups, admins, sender) -> None:
    if message.from_user is None:
        return
    allowed, error = await permitted(admins, message.chat.id, message.from_user.id)
    if not allowed:
        await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, error))
        return
    chat = await groups.get(message.chat.id)
    if chat is None or not chat.bot_is_admin:
        await sender.send(
            message.chat.id, lambda: bot.send_message(message.chat.id, texts.NEED_ADMIN)
        )
        return
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id, texts.SETTINGS_TITLE, reply_markup=settings_keyboard(chat)
        ),
    )


async def settings_callback(
    query: CallbackQuery,
    bot: Bot,
    groups,
    admins,
    sender,
    setting_prompts,
) -> None:
    if not isinstance(query.message, Message) or query.message.chat.type not in {
        "group",
        "supergroup",
    }:
        return
    chat_id = query.message.chat.id
    allowed, error = await permitted(admins, chat_id, query.from_user.id)
    if not allowed:
        await sender.answer_callback_query(bot, query.id, text=error, show_alert=True)
        return
    await sender.answer_callback_query(bot, query.id)
    pieces = (query.data or "").split(":", 2)
    operation = pieces[0]
    field = pieces[1] if len(pieces) > 1 else ""
    chat = await groups.get(chat_id)
    if chat is None or not chat.bot_is_admin:
        return
    if operation == "sf" and field in texts.SETTING_LABELS:
        markup = setting_choices(field)
    elif operation == "sp" and field in INPUT_FIELDS:
        sent = await sender.send(
            chat_id,
            lambda: bot.send_message(
                chat_id,
                texts.setting_prompt(field, query.from_user),
                reply_markup=ForceReply(selective=True),
                reply_parameters={"message_id": query.message.message_id},
            ),
        )
        if sent is not None:
            setting_prompts.put(chat_id, query.from_user.id, field, sent.message_id)
        return
    elif operation == "sv" and len(pieces) == 3:
        try:
            value = parse_setting(field, pieces[2])
        except ValueError:
            return
        chat = await groups.change_setting(chat_id, field, value)
        if chat is None:
            return
        markup = settings_keyboard(chat)
    elif operation == "settings":
        markup = settings_keyboard(chat)
    else:
        return
    await sender.send(
        chat_id,
        lambda: bot.edit_message_text(
            texts.SETTINGS_TITLE,
            chat_id=chat_id,
            message_id=query.message.message_id,
            reply_markup=markup,
        ),
    )


class PendingSettingReply(Filter):
    async def __call__(self, message: Message, setting_prompts=None) -> bool | dict:
        if (
            setting_prompts is None
            or message.from_user is None
            or message.reply_to_message is None
            or not message.text
        ):
            return False
        field = setting_prompts.get(
            message.chat.id, message.from_user.id, message.reply_to_message.message_id
        )
        return {"setting_field": field} if field else False


async def setting_reply(
    message: Message, bot: Bot, groups, admins, sender, setting_prompts, setting_field: str
) -> None:
    allowed, error = await permitted(admins, message.chat.id, message.from_user.id)
    if not allowed:
        setting_prompts.clear(message.chat.id, message.from_user.id)
        await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, error))
        return
    try:
        value = parse_setting(setting_field, message.text)
    except ValueError:
        await sender.send(
            message.chat.id, lambda: bot.send_message(message.chat.id, texts.SETTINGS_INVALID)
        )
        return
    chat = await groups.change_setting(message.chat.id, setting_field, value)
    setting_prompts.clear(message.chat.id, message.from_user.id)
    if chat is not None:
        await sender.send(
            message.chat.id,
            lambda: bot.send_message(
                message.chat.id, texts.SETTINGS_SAVED, reply_markup=settings_keyboard(chat)
            ),
        )


def create_router() -> Router:
    router = Router(name="settings")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.message.register(settings, Command("sozlamalar"))
    router.message.register(setting_reply, PendingSettingReply())
    router.callback_query.register(settings_callback, F.data.regexp(r"^(settings$|s[fvp]:)"))
    return router
