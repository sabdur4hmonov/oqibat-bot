"""UTC is used for all persisted timestamps."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)
