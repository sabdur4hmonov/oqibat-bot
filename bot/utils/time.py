"""UTC is used for all persisted timestamps."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_quiet(now: datetime, tz: str, start: time, end: time) -> bool:
    local = now.astimezone(ZoneInfo(tz)).time().replace(tzinfo=None)
    if start == end:
        return False
    return start <= local < end if start < end else local >= start or local < end


def after_quiet(now: datetime, tz: str, start: time, end: time) -> datetime:
    if not is_quiet(now, tz, start, end):
        return now
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    result = datetime.combine(local.date(), end, zone)
    if result.astimezone(UTC) <= now:
        result += timedelta(days=1)
    return result.astimezone(UTC)
