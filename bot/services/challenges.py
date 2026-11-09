"""Challenge orchestration. State/ledger changes precede Telegram I/O."""

from bot import texts
from bot.db.models import Chat
from bot.services.effects import Effects
from bot.services.sender import Priority
from bot.utils.time import after_quiet, is_quiet, utc_now

KIND_ALIASES = {"video": "video_note", "ovoz": "voice", "surat": "photo", "matn": "text"}


def message_kind(message) -> str | None:
    for kind in ("video_note", "voice", "photo", "text"):
        if getattr(message, kind, None):
            return kind
    return None


class ChallengeService:
    def __init__(
        self, sessions, bot, sender, repository, pending, content, penalties, effects=None
    ) -> None:
        self.sessions, self.bot, self.sender = sessions, bot, sender
        self.repo, self.pending, self.content, self.penalties = (
            repository,
            pending,
            content,
            penalties,
        )
        self.recovery = None
        self.early_messages = {}
        self.effects = effects or Effects()

    async def assign(
        self,
        chat_id: int,
        kind=None,
        *,
        force=False,
        now=None,
        target=None,
        hours=None,
        game_id=None,
    ):
        chat_id = self.repo.locks.resolve(chat_id)
        now = now or utc_now()
        async with self.sessions() as session:
            chat = await session.get(Chat, chat_id)
        if chat is None or not chat.is_active or not chat.bot_is_admin:
            return texts.NEED_ADMIN
        if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
            return texts.QUIET_ASSIGN
        if self.pending.for_chat(chat_id):
            return texts.PENDING_CHALLENGE
        result = await self.repo.assign(
            chat_id,
            now,
            self.content.banks["challenges"],
            kind,
            force,
            target=target,
            hours=hours,
            game_id=game_id,
        )
        if result is None:
            return texts.NO_CHALLENGE_CANDIDATE
        challenge, user, chat, item = result
        if self.recovery:
            sent = await self.recovery.challenge(challenge.id, now=now)
        else:
            sent = await self.sender.send(
                chat_id,
                lambda: self.bot.send_message(
                    chat_id,
                    texts.challenge_post(
                        user.id, user.first_name, item["text"], challenge.deadline_at, chat.tz
                    ),
                ),
                priority=Priority.CHALLENGE,
            )
        if sent is None:
            await self.repo.resolve(chat_id, challenge.id, "cancelled")
            self.early_messages.pop(challenge.id, None)
            return texts.CHALLENGE_SEND_FAILED
        await self.repo.set_message(
            chat_id,
            challenge.id,
            sent.message_id,
            getattr(getattr(sent, "chat", None), "id", chat_id),
        )
        early = self.early_messages.pop(challenge.id, None)
        if early is not None:
            await self.complete(early)
        return None

    async def scheduled(self, chat, now):
        if is_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end):
            return after_quiet(now, chat.tz, chat.quiet_start, chat.quiet_end)
        outcome = await self.assign(chat.id, now=now)
        return outcome not in {texts.CHALLENGE_SEND_FAILED, texts.NEED_ADMIN}

    async def complete(self, message) -> bool:
        if message.from_user is None or message.from_user.is_bot:
            return False
        kind = message_kind(message)
        if kind is None:
            return False
        chat_id = self.repo.locks.resolve(message.chat.id)
        challenge_id = self.pending.match(chat_id, message.from_user.id, kind, message.date)
        if challenge_id is None:
            return False
        posted_id = self.pending.message_ids.get(challenge_id)
        if posted_id is None:
            self.early_messages[challenge_id] = message
            return False
        if message.message_id <= posted_id:
            return False
        delta = await self.repo.complete(
            chat_id,
            challenge_id,
            message.from_user.id,
            kind,
            message.date,
            message.message_id,
        )
        if delta is None:
            return False
        if self.recovery:
            await self.recovery.challenge(challenge_id, result=True)
            return True
        await self.sender.send(
            message.chat.id,
            lambda: self.bot.send_message(
                message.chat.id,
                texts.challenge_done(message.from_user.id, message.from_user.first_name, delta),
            ),
            priority=Priority.CHALLENGE,
        )
        return True

    async def expire(self, challenge, now) -> bool:
        result = await self.repo.expire(challenge.chat_id, challenge.id, now)
        self.early_messages.pop(challenge.id, None)
        if result is None:
            return False
        chat, user_id, misses = result
        self.effects.start(self._notify_expiry(chat, user_id, misses, challenge.id))
        return True

    async def _notify_expiry(self, chat, user_id, misses, challenge_id=None) -> None:
        await self.penalties.apply(chat, user_id, misses)
        if self.recovery and challenge_id is not None:
            await self.recovery.challenge(challenge_id, result=True)
            return
        await self.sender.send(
            chat.id,
            lambda: self.bot.send_message(
                chat.id, texts.challenge_missed(user_id, chat.penalty_mode)
            ),
            priority=Priority.CHALLENGE,
        )
