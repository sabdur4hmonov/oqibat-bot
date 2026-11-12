"""Bounded, sanitized operational notices; no exception messages are retained."""

import asyncio
import logging
import re
import time

from bot import texts
from bot.services.sender import Priority
from bot.utils.time import utc_now

logger = logging.getLogger(__name__)
INTERVAL = 600
SOURCES = {
    "handler",
    "sender",
    "background",
    "scheduler.tick",
    "scheduler.deadlines",
    "scheduler.daily",
    "scheduler.weekly",
    "scheduler.season",
    "scheduler.challenge",
    "scheduler.expire",
    "scheduler.game",
    "other",
}


class ErrorAlerts:
    def __init__(self, bot, sender, owner_id, *, clock=time.monotonic, utc_clock=utc_now):
        self.bot, self.sender, self.owner_id = bot, sender, owner_id
        self.clock, self.utc_clock = clock, utc_clock
        self.pending = 0
        self.latest = None
        self.next_at = 0.0
        self.sending = False
        self.wake = asyncio.Event()

    def record(self, error, where, chat_id=None, *, count=1):
        if not self.owner_id:
            return
        try:
            name = type(error).__name__
            name = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name) else "Exception"
            self.latest = {
                "type": name,
                "where": where if where in SOURCES else "other",
                "chat_id": chat_id
                if type(chat_id) is int and -(2**63) <= chat_id < 2**63
                else None,
                "at": self.utc_clock(),
            }
            self.pending += count if type(count) is int and count > 0 else 1
            self.wake.set()
        except Exception:
            logger.warning("Owner error summary could not be recorded")

    async def flush(self):
        if not self.owner_id or not self.pending or self.sending or self.clock() < self.next_at:
            return False
        count, summary = self.pending, dict(self.latest)
        self.pending = 0
        self.sending = True
        self.next_at = self.clock() + INTERVAL
        delivered = False

        async def operation():
            self.next_at = self.clock() + INTERVAL
            return await self.bot.send_message(
                self.owner_id, texts.owner_error_alert(summary, count)
            )

        try:
            delivered = (
                await self.sender.send(
                    self.owner_id, operation, priority=Priority.CHALLENGE, report_failures=False
                )
                is not None
            )
        except Exception:
            logger.warning("Owner error alert could not be delivered")
        finally:
            # Start the next window after confirmation/failure, too: a slow
            # Telegram response must never shorten the delivery interval.
            self.next_at = max(self.next_at, self.clock() + INTERVAL)
            if not delivered:
                self.pending += count
            self.sending = False
            if self.pending:
                self.wake.set()
        return delivered

    async def run(self):
        while True:
            if not self.pending:
                await self.wake.wait()
            self.wake.clear()
            delay = max(0, self.next_at - self.clock())
            if delay:
                await asyncio.sleep(delay)
            await self.flush()
