"""Pure, stable local-time spreading; all results are aware UTC datetimes."""

import hashlib
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


def stable_offset(chat_id: int, kind: str) -> int:
    maximum = {"daily": 901, "weekly": 3600}[kind]
    digest = hashlib.blake2b(f"oqibat:{kind}:{chat_id}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % maximum


def next_daily(chat_id: int, tz: str, daily_time: time, after: datetime) -> datetime:
    zone = ZoneInfo(tz)
    local = after.astimezone(zone)
    for day in range(3):
        candidate = datetime.combine(local.date() + timedelta(days=day), daily_time, zone)
        candidate = (candidate + timedelta(seconds=stable_offset(chat_id, "daily"))).astimezone(UTC)
        if candidate > after:
            return candidate
    raise ValueError("Could not compute next daily time")


def next_weekly(chat_id: int, tz: str, after: datetime) -> datetime:
    zone = ZoneInfo(tz)
    local = after.astimezone(zone)
    sunday = local.date() + timedelta(days=(6 - local.weekday()) % 7)
    candidate = datetime.combine(sunday, time(20), zone)
    candidate += timedelta(seconds=stable_offset(chat_id, "weekly"))
    if candidate.astimezone(UTC) <= after:
        candidate += timedelta(days=7)
    return candidate.astimezone(UTC)


def next_challenge(
    tz: str,
    count: int,
    quiet_start: time,
    quiet_end: time,
    after: datetime,
) -> datetime | None:
    if count == 0:
        return None
    zone = ZoneInfo(tz)
    local = after.astimezone(zone)
    for day in range(-1, 3):
        date = local.date() + timedelta(days=day)
        start = datetime.combine(date, quiet_end, zone)
        end = datetime.combine(date, quiet_start, zone)
        if end <= start:
            end += timedelta(days=1)
        for slot in range(count):
            candidate = start + (end - start) * ((slot + 0.5) / count)
            if candidate.astimezone(UTC) > after:
                return candidate.astimezone(UTC)
    raise ValueError("Could not compute next challenge time")


def next_for_chat(kind: str, chat, now: datetime) -> datetime | None:
    if not chat.is_active or not chat.bot_is_admin:
        return None
    if kind == "daily":
        return next_daily(chat.id, chat.tz, chat.daily_time, now) if chat.daily_enabled else None
    if kind == "weekly":
        return next_weekly(chat.id, chat.tz, now)
    if kind == "challenge":
        return next_challenge(
            chat.tz, chat.challenges_per_day, chat.quiet_start, chat.quiet_end, now
        )
    raise ValueError("Unknown schedule kind")
