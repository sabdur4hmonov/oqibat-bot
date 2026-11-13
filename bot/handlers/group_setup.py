from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message

from bot import texts
from bot.keyboards.private import group_keyboard
from bot.services.onboarding import setup_keyboard
from bot.utils.admin import member_is_active, member_is_admin


async def bot_membership(event: ChatMemberUpdated, sender, groups, quick_setup) -> None:
    if event.chat.type not in {"group", "supergroup"}:
        return
    chat = await groups.bot_membership(event.chat, event.new_chat_member)
    if not chat.is_active:
        return
    was_active = member_is_active(event.old_chat_member)
    was_admin = member_is_admin(event.old_chat_member)
    if not was_active or was_admin != chat.bot_is_admin:
        text = texts.WELCOME_GROUP if chat.bot_is_admin else texts.NEED_ADMIN
        sent = await sender.send(
            chat.id,
            lambda: event.bot.send_message(
                chat.id, text, reply_markup=setup_keyboard(0) if chat.bot_is_admin else None
            ),
        )
        if chat.bot_is_admin and sent:
            quick_setup.remember(chat.id, sent.message_id)


async def setup_button(query, quick_setup):
    await quick_setup.callback(query)


async def member_update(event: ChatMemberUpdated, groups) -> None:
    if event.chat.type not in {"group", "supergroup"} or event.new_chat_member.user.is_bot:
        return
    await groups.membership(
        event.chat.id, event.new_chat_member.user, active=member_is_active(event.new_chat_member)
    )


async def migrate_chat(message: Message, migrations) -> None:
    if message.migrate_to_chat_id:
        await migrations.migrate(message.chat.id, message.migrate_to_chat_id)
    elif message.migrate_from_chat_id:
        await migrations.migrate(message.migrate_from_chat_id, message.chat.id)


async def join(message: Message, bot: Bot, sender, groups) -> None:
    if message.from_user is None or message.from_user.is_bot:
        return
    try:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        permitted = member_is_active(member)
    except Exception:
        permitted = False
    if not permitted:
        await sender.send(
            message.chat.id, lambda: bot.send_message(message.chat.id, texts.MEMBER_CHECK_FAILED)
        )
        return
    success = await groups.membership(message.chat.id, message.from_user, opted_in=True)
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id,
            texts.JOINED if success else texts.NEED_ADMIN,
        ),
    )


async def join_button(query: CallbackQuery, bot: Bot, sender, groups) -> None:
    if query.message is None or query.message.chat.type not in {"group", "supergroup"}:
        return
    try:
        member = await bot.get_chat_member(query.message.chat.id, query.from_user.id)
        permitted = member_is_active(member) and not query.from_user.is_bot
    except Exception:
        permitted = False
    if not permitted:
        await sender.answer_callback_query(
            bot, query.id, text=texts.MEMBER_CHECK_FAILED, show_alert=True
        )
        return
    success = await groups.membership(query.message.chat.id, query.from_user, opted_in=True)
    await sender.answer_callback_query(
        bot, query.id, text=texts.JOINED if success else texts.NEED_ADMIN, show_alert=True
    )


async def leave(message: Message, bot: Bot, sender, groups) -> None:
    if message.from_user is None:
        return
    await groups.membership(message.chat.id, message.from_user, opted_in=False)
    await sender.send(message.chat.id, lambda: bot.send_message(message.chat.id, texts.OPTED_OUT))


async def help_group(message: Message, bot: Bot, sender, settings) -> None:
    await sender.send(
        message.chat.id,
        lambda: bot.send_message(
            message.chat.id,
            texts.group_help(settings.instagram_handle),
            reply_markup=group_keyboard(settings, message.chat.id),
        ),
    )


def create_router() -> Router:
    router = Router(name="group_setup")
    router.message.filter(F.chat.type.in_({"group", "supergroup"}))
    router.my_chat_member.register(bot_membership)
    router.chat_member.register(member_update)
    router.message.register(migrate_chat, F.migrate_to_chat_id | F.migrate_from_chat_id)
    router.message.register(join, Command("qoshilish"))
    router.message.register(leave, Command("chiqish"))
    router.message.register(help_group, Command("help"))
    router.callback_query.register(join_button, F.data == "join")
    router.callback_query.register(setup_button, F.data.startswith("qs:"))
    return router
