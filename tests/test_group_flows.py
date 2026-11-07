from datetime import UTC, datetime

import pytest
from aiogram import Bot
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetChatAdministrators,
    GetChatMember,
)
from aiogram.types import ChatMemberAdministrator, ChatMemberMember, Message, Update, User
from test_private_and_startup import TOKEN, LocalTelegram

from bot import texts
from bot.__main__ import create_dispatcher
from bot.db.models import Chat, Membership
from bot.services.runtime import ScaleMiddleware, ScaleRuntime


def tg_user(user_id=42, bot=False):
    return User(id=user_id, first_name="<Sinov>", is_bot=bot)


def administrator(user):
    flags = {
        key: False
        for key, field in ChatMemberAdministrator.model_fields.items()
        if field.is_required() and key != "user"
    }
    return ChatMemberAdministrator(user=user, **flags)


class GroupTelegram(LocalTelegram):
    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(
            method, (GetChatAdministrators, GetChatMember, AnswerCallbackQuery, EditMessageText)
        ):
            self.methods.append(method)
            if isinstance(method, GetChatAdministrators):
                return [administrator(tg_user())]
            if isinstance(method, GetChatMember):
                return ChatMemberMember(user=tg_user(method.user_id))
            if isinstance(method, AnswerCallbackQuery):
                return True
            return Message(
                message_id=method.message_id,
                date=datetime.now(UTC),
                chat={"id": method.chat_id, "type": "group"},
                text=method.text,
            )
        return await super().make_request(bot, method, timeout=timeout)


def bot_update(status, old="left"):
    user = tg_user(123456789, True)
    new = (
        administrator(user).model_dump()
        if status == "administrator"
        else {"status": status, "user": user.model_dump()}
    )
    previous = (
        administrator(user).model_dump()
        if old == "administrator"
        else {"status": old, "user": user.model_dump()}
    )
    return Update.model_validate(
        {
            "update_id": 1,
            "my_chat_member": {
                "chat": {"id": -1, "type": "group", "title": "<Sinov>"},
                "from": tg_user().model_dump(),
                "date": 1794024000,
                "old_chat_member": previous,
                "new_chat_member": new,
            },
        }
    )


def callback(data, user=42):
    return Update.model_validate(
        {
            "update_id": 2,
            "callback_query": {
                "id": "callback1",
                "from": tg_user(user).model_dump(),
                "chat_instance": "instance",
                "data": data,
                "message": {
                    "message_id": 100,
                    "date": 1794024000,
                    "chat": {"id": -1, "type": "group"},
                    "text": "menu",
                },
            },
        }
    )


@pytest.fixture
async def group_app(sessions, settings):
    transport = GroupTelegram()
    async with Bot(TOKEN, session=transport) as bot:
        async with ScaleRuntime(sessions, bot) as runtime:
            dispatcher = create_dispatcher()
            dispatcher.update.outer_middleware(ScaleMiddleware(runtime))

            async def feed(update):
                return await dispatcher.feed_update(
                    bot, update, settings=settings, sessions=sessions, **runtime.workflow()
                )

            yield feed, transport, runtime


async def test_add_without_admin_promote_remove_readd(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("member"))
    assert transport.methods[-1].text == texts.NEED_ADMIN
    await feed(bot_update("administrator", "member"))
    assert transport.methods[-1].text == texts.WELCOME_GROUP
    assert transport.methods[-1].reply_markup.inline_keyboard[0][0].callback_data == "join"
    await feed(bot_update("left", "administrator"))
    async with sessions() as session:
        assert not (await session.get(Chat, -1)).is_active
    await feed(bot_update("administrator"))
    async with sessions() as session:
        chat = await session.get(Chat, -1)
        assert chat.is_active and chat.bot_is_admin and chat.next_daily_at is not None


async def test_opt_in_and_out_preserve_consent(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await feed(callback("join"))
    assert transport.methods[-1].text == texts.JOINED
    async with sessions() as session:
        assert (await session.get(Membership, (-1, 42))).opted_in
    await runtime.groups.membership(-1, tg_user(), opted_in=False)
    async with sessions() as session:
        assert not (await session.get(Membership, (-1, 42))).opted_in


async def test_non_admin_settings_popup_and_admin_setting_update(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await feed(callback("sv:challenges_per_day:3", user=77))
    assert isinstance(transport.methods[-1], AnswerCallbackQuery)
    assert transport.methods[-1].show_alert and transport.methods[-1].text == texts.ADMINS_ONLY
    async with sessions() as session:
        assert (await session.get(Chat, -1)).challenges_per_day == 1
    await feed(callback("sv:challenges_per_day:3"))
    async with sessions() as session:
        assert (await session.get(Chat, -1)).challenges_per_day == 3
    assert isinstance(transport.methods[-1], EditMessageText)


async def test_reply_setting_edits_time_and_escapes_user(group_app, sessions):
    feed, transport, runtime = group_app
    await feed(bot_update("administrator"))
    await feed(callback("sp:daily_time"))
    assert "&lt;Sinov&gt;" in transport.methods[-1].text
    await feed(
        Update.model_validate(
            {
                "update_id": 3,
                "message": {
                    "message_id": 101,
                    "date": 1794024000,
                    "chat": {"id": -1, "type": "group"},
                    "from": tg_user().model_dump(),
                    "text": "22:15",
                    "reply_to_message": {
                        "message_id": 100,
                        "date": 1794024000,
                        "chat": {"id": -1, "type": "group"},
                        "text": "prompt",
                    },
                },
            }
        )
    )
    async with sessions() as session:
        assert (await session.get(Chat, -1)).daily_time.strftime("%H:%M") == "22:15"
