from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services.penalties import Penalties
from bot.services.sender import Sender
from bot.utils.time import utc_now


@pytest.fixture
async def moderation():
    bot = SimpleNamespace(
        id=999,
        get_chat_member=AsyncMock(
            return_value=SimpleNamespace(status="administrator", can_restrict_members=True)
        ),
        get_chat=AsyncMock(return_value=SimpleNamespace(type="supergroup")),
        restrict_chat_member=AsyncMock(return_value=True),
        ban_chat_member=AsyncMock(return_value=True),
        unban_chat_member=AsyncMock(return_value=True),
    )
    admins = SimpleNamespace(get=AsyncMock(return_value=frozenset({7})))
    sender = Sender(None)
    service = Penalties(bot, sender, admins, owner_id=1)

    async def member(chat_id, user_id):
        if user_id == bot.id:
            return bot.get_chat_member.return_value
        return SimpleNamespace(status="member")

    bot.get_chat_member.side_effect = member
    try:
        yield service, bot
    finally:
        await sender.close()


@pytest.mark.parametrize("user", [1, 7])
async def test_admins_and_configured_owner_are_never_muted_or_kicked(moderation, user):
    service, bot = moderation
    for mode in ("mute", "kick"):
        await service.apply(
            SimpleNamespace(id=-1, penalty_mode=mode, kick_after_misses=3, mute_days=3), user, 5
        )
    bot.restrict_chat_member.assert_not_awaited()
    bot.ban_chat_member.assert_not_awaited()


async def test_mute_deadline_and_kick_immediate_unban(moderation):
    service, bot = moderation
    chat = SimpleNamespace(id=-1, penalty_mode="mute", mute_days=3, kick_after_misses=3)
    await service.apply(chat, 2, 1)
    args = bot.restrict_chat_member.await_args.kwargs
    assert args["permissions"].can_send_messages is False
    assert 30 < (args["until_date"] - utc_now()).total_seconds() < 366 * 86400
    chat.penalty_mode = "kick"
    await service.apply(chat, 2, 2)
    bot.ban_chat_member.assert_not_awaited()
    await service.apply(chat, 2, 3)
    bot.ban_chat_member.assert_awaited_once()
    assert (
        30
        < (bot.ban_chat_member.await_args.kwargs["until_date"] - utc_now()).total_seconds()
        <= 300
    )
    bot.unban_chat_member.assert_awaited_once_with(-1, 2, only_if_banned=True)


async def test_no_rights_or_basic_group_skip_moderation(moderation):
    service, bot = moderation
    chat = SimpleNamespace(id=-1, penalty_mode="mute", mute_days=3, kick_after_misses=3)
    bot.get_chat_member.return_value.can_restrict_members = False
    await service.apply(chat, 2, 1)
    bot.get_chat_member.return_value.can_restrict_members = True
    bot.get_chat.return_value.type = "group"
    await service.apply(chat, 2, 1)
    bot.restrict_chat_member.assert_not_awaited()


async def test_fresh_promotion_is_protected_even_with_stale_admin_cache(moderation):
    service, bot = moderation
    bot.get_chat_member.side_effect = None
    bot.get_chat_member.return_value = SimpleNamespace(
        status="administrator", can_restrict_members=True
    )
    await service.apply(
        SimpleNamespace(id=-1, penalty_mode="kick", mute_days=3, kick_after_misses=3), 2, 3
    )
    bot.ban_chat_member.assert_not_awaited()
