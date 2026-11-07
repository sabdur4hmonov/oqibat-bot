"""Pure setting validation and short-lived reply prompts (no per-message SQL)."""

import re
import time
from datetime import time as local_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CHOICES = {
    "daily_enabled": ("1", "0"),
    "challenges_per_day": ("0", "1", "2", "3"),
    "challenge_hours": ("2", "6", "10", "24"),
    "penalty_mode": ("off", "points", "mute", "kick"),
    "mute_days": ("1", "3", "7"),
}
INPUT_FIELDS = {"tz", "daily_time", "quiet_start", "quiet_end", "kick_after_misses"}


def parse_setting(field: str, raw: str):
    raw = raw.strip()
    if field in CHOICES:
        if raw not in CHOICES[field]:
            raise ValueError("Invalid setting choice")
        if field == "penalty_mode":
            return raw
        return raw == "1" if field == "daily_enabled" else int(raw)
    if field == "tz":
        try:
            ZoneInfo(raw)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Invalid timezone") from None
        return raw
    if field in {"daily_time", "quiet_start", "quiet_end"}:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw):
            raise ValueError("Use HH:MM")
        return local_time.fromisoformat(raw)
    if field == "kick_after_misses" and raw.isascii() and raw.isdecimal() and 1 <= int(raw) <= 100:
        return int(raw)
    raise ValueError("Unknown setting or invalid value")


class SettingPrompts:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.pending: dict[tuple[int, int], tuple[str, int, float]] = {}

    def put(self, chat: int, user: int, field: str, message_id: int) -> None:
        now = self.clock()
        self.pending = {key: value for key, value in self.pending.items() if value[2] > now}
        self.pending[(chat, user)] = (field, message_id, now + 300)

    def get(self, chat: int, user: int, reply_id: int | None) -> str | None:
        item = self.pending.get((chat, user))
        if item is None:
            return None
        if item[2] <= self.clock():
            self.pending.pop((chat, user), None)
            return None
        return item[0] if item[1] == reply_id else None

    def clear(self, chat: int, user: int) -> None:
        self.pending.pop((chat, user), None)
