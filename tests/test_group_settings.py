from datetime import time
from types import SimpleNamespace

import pytest

from bot.services.settings import CHOICES, SettingPrompts, parse_setting
from bot.utils.admin import member_is_active, member_is_admin


@pytest.mark.parametrize(
    "field,raw,expected",
    [
        ("tz", "Asia/Tashkent", "Asia/Tashkent"),
        ("daily_time", "23:59", time(23, 59)),
        ("quiet_start", "00:00", time()),
        ("quiet_end", "08:00", time(8)),
        ("daily_enabled", "0", False),
        ("daily_enabled", "1", True),
        ("challenges_per_day", "3", 3),
        ("challenge_hours", "24", 24),
        ("mute_days", "7", 7),
        ("penalty_mode", "kick", "kick"),
        ("kick_after_misses", "100", 100),
    ],
)
def test_parse_setting(field, raw, expected):
    assert parse_setting(field, raw) == expected


@pytest.mark.parametrize(
    "field,raw",
    [
        ("id", "42"),
        ("tz", "Unknown/Zone"),
        ("daily_time", "25:00"),
        ("quiet_end", "9:00"),
        ("quiet_start", "10:99"),
        ("daily_enabled", "yes"),
        ("challenges_per_day", "4"),
        ("challenge_hours", "5"),
        ("mute_days", "2"),
        ("penalty_mode", "ban_everyone"),
        ("kick_after_misses", "0"),
        ("kick_after_misses", "101"),
    ],
)
def test_invalid_setting_rejected(field, raw):
    with pytest.raises(ValueError):
        parse_setting(field, raw)


def test_every_inline_choice_is_valid():
    for field, choices in CHOICES.items():
        for raw in choices:
            parse_setting(field, raw)


def test_prompts_are_bound_to_user_chat_reply_and_expire(fake_clock):
    prompts = SettingPrompts(clock=fake_clock.now)
    prompts.put(-1, 42, "tz", 100)
    assert prompts.get(-1, 42, 100) == "tz"
    assert prompts.get(-2, 42, 100) is None
    assert prompts.get(-1, 77, 100) is None
    assert prompts.get(-1, 42, 99) is None
    fake_clock.value = 301
    assert prompts.get(-1, 42, 100) is None


@pytest.mark.parametrize(
    "status,active,admin",
    [
        ("creator", True, True),
        ("administrator", True, True),
        ("member", True, False),
        ("left", False, False),
        ("kicked", False, False),
        ("restricted", False, False),
    ],
)
def test_membership_predicates(status, active, admin):
    member = SimpleNamespace(status=status, is_member=False)
    assert member_is_active(member) == active
    assert member_is_admin(member) == admin
