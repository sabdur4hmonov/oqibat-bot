import random
from datetime import UTC, datetime, time

import pytest

from bot.services.content import choose_content, validate_bank
from bot.utils.time import after_quiet, is_quiet


def test_content_empty_3000_and_no_repeat_until_all_used():
    assert choose_content([], {}) is None
    items = [{"key": str(i), "text": "Salom {group}"} for i in range(3000)]
    assert len(validate_bank("daily_messages", items)) == 3000
    used = {}
    rng = random.Random(4)
    small = items[:3]
    for age in range(3):
        item = choose_content(small, used, rng)
        assert item["key"] not in used
        used[item["key"]] = age
    assert choose_content(small, used, rng)["key"] == min(used, key=used.get)


@pytest.mark.parametrize(
    "items",
    [
        {},
        [{"key": "a"}],
        [{"key": "a", "text": ""}],
        [{"key": "a", "text": "ok"}, {"key": "a", "text": "again"}],
    ],
)
def test_bad_content_rejected(items):
    with pytest.raises(ValueError):
        validate_bank("daily_messages", items)


@pytest.mark.parametrize("hour,quiet", [(17, False), (18, True), (23, True), (2, True), (3, False)])
def test_tashkent_overnight_quiet_window(hour, quiet):
    now = datetime(2026, 11, 7, hour, tzinfo=UTC)
    assert is_quiet(now, "Asia/Tashkent", time(23), time(8)) == quiet
    result = after_quiet(now, "Asia/Tashkent", time(23), time(8))
    assert result >= now
    assert not is_quiet(result, "Asia/Tashkent", time(23), time(8))


def test_equal_quiet_boundaries_disable_quiet_and_same_day_window():
    now = datetime(2026, 11, 7, 10, tzinfo=UTC)
    assert not is_quiet(now, "UTC", time(), time())
    assert after_quiet(now, "UTC", time(9), time(11)) == now.replace(hour=11)
