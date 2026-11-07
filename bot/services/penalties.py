"""Permission-safe moderation, outside all state/database locks."""

import logging
from datetime import timedelta

from aiogram.types import ChatPermissions

from bot.services.sender import Priority
from bot.utils.time import after_quiet, utc_now

logger = logging.getLogger(__name__)


def challenge_deadline(now, hours, tz, quiet_start, quiet_end):
    return after_quiet(now + timedelta(hours=hours), tz, quiet_start, quiet_end)


def should_restrict(
    mode: str, user_id: int, owner_id: int, admins: set | frozenset, misses: int, threshold: int
) -> bool:
    return (
        mode in {"mute", "kick"}
        and user_id != owner_id
        and user_id not in admins
        and (mode != "kick" or misses >= threshold)
    )


class Penalties:
    def __init__(self, bot, sender, admins, owner_id: int) -> None:
        self.bot, self.sender, self.admins, self.owner_id = bot, sender, admins, owner_id

    async def apply(self, chat, user_id: int, misses: int) -> None:
        if not self.owner_id or chat.penalty_mode not in {"mute", "kick"}:
            return
        try:
            admins = await self.admins.get(chat.id)
            if not should_restrict(
                chat.penalty_mode, user_id, self.owner_id, admins, misses, chat.kick_after_misses
            ):
                return
            me = await self.bot.get_chat_member(chat.id, self.bot.id)
            if me.status != "administrator" or not me.can_restrict_members:
                return
            details = await self.bot.get_chat(chat.id)
            if details.type != "supergroup":
                logger.warning("Automatic mute/kick requires a supergroup: %s", chat.id)
                return
        except Exception:
            logger.exception("Permission check failed; moderation skipped for chat %s", chat.id)
            return

        async def guarded(operation):
            target = await self.bot.get_chat_member(chat.id, user_id)
            if target.status in {"administrator", "creator"}:
                return False
            return await operation()

        if chat.penalty_mode == "mute":
            permissions = ChatPermissions(
                **{
                    name: False
                    for name in ChatPermissions.model_fields
                    if name.startswith("can_send_")
                },
                can_add_web_page_previews=False,
            )
            await self.sender.send(
                chat.id,
                lambda: guarded(
                    lambda: self.bot.restrict_chat_member(
                        chat.id,
                        user_id,
                        permissions=permissions,
                        use_independent_chat_permissions=True,
                        until_date=utc_now() + timedelta(days=chat.mute_days),
                    )
                ),
                priority=Priority.CHALLENGE,
            )
        else:
            banned = await self.sender.send(
                chat.id,
                lambda: guarded(
                    lambda: self.bot.ban_chat_member(
                        chat.id,
                        user_id,
                        until_date=utc_now() + timedelta(minutes=5),
                    )
                ),
                priority=Priority.CHALLENGE,
            )
            if banned is True:
                # Expiring ban is a failsafe if the immediate unban request cannot be delivered.
                await self.sender.send(
                    chat.id,
                    lambda: self.bot.unban_chat_member(
                        chat.id,
                        user_id,
                        only_if_banned=True,
                    ),
                    priority=Priority.GAME,
                )
