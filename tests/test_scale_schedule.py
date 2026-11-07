from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from bot.services.schedule_times import next_challenge, next_daily, next_weekly, stable_offset


@pytest.mark.parametrize("kind,upper", [("daily", 900), ("weekly", 3599)])
def test_stable_offsets_cover_window(kind, upper):
    offsets = [stable_offset(-1000000 - i, kind) for i in range(5000)]
    assert offsets == [stable_offset(-1000000 - i, kind) for i in range(5000)]
    assert min(offsets) >= 0 and max(offsets) <= upper
    assert len(set(offsets)) > upper * 0.65
    assert sum(offsets) / len(offsets) == pytest.approx(upper / 2, rel=0.05)


def test_daily_utc_offset_and_no_same_day_duplicate():
    now = datetime(2026, 11, 7, 0, tzinfo=UTC)
    due = next_daily(-123, "Asia/Tashkent", time(9), now)
    assert due == now.replace(hour=4) + timedelta(seconds=stable_offset(-123, "daily"))
    assert next_daily(-123, "Asia/Tashkent", time(9), due) == due + timedelta(days=1)


def test_weekly_is_sunday_between_20_and_21():
    now = datetime(2026, 11, 7, 0, tzinfo=UTC)
    for chat in range(-100, 0):
        due = next_weekly(chat, "Asia/Tashkent", now)
        local = due.astimezone(ZoneInfo("Asia/Tashkent"))
        assert local.weekday() == 6 and local.hour == 20
        assert next_weekly(chat, "Asia/Tashkent", due) == due + timedelta(days=7)


def test_daily_recomputes_local_clock_across_dst():
    before = datetime(2026, 10, 24, 7, tzinfo=UTC)
    first = next_daily(-12, "Europe/Berlin", time(9), before)
    second = next_daily(-12, "Europe/Berlin", time(9), first)
    assert second - first == timedelta(hours=25)


def test_challenge_slots_stay_outside_quiet_hours():
    now = datetime(2026, 11, 7, 0, tzinfo=UTC)
    assert next_challenge("Asia/Tashkent", 0, time(23), time(8), now) is None
    times = []
    for _ in range(6):
        now = next_challenge("Asia/Tashkent", 3, time(23), time(8), now)
        local = now.astimezone(ZoneInfo("Asia/Tashkent"))
        assert 8 <= local.hour < 23
        times.append(now)
    assert times[3] - times[0] == timedelta(days=1)
