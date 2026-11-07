from datetime import UTC, datetime, time, timedelta

import pytest

from bot.services.penalties import challenge_deadline, should_restrict
from bot.services.picker import Candidate, pick_member
from bot.services.points import CHALLENGE_DONE, challenge_points
from bot.utils.time import week_start

NOW = datetime(2026, 11, 7, 16, tzinfo=UTC)


class ChooseHeaviest:
    def choices(self, population, weights, k):
        assert k == 1
        return [population[weights.index(max(weights))]]


def test_picker_eligibility_recent_exclusion_and_fallback():
    assert (
        pick_member(
            [Candidate(1, opted_in=False), Candidate(2, active=False), Candidate(3, pending=True)],
            NOW,
        )
        is None
    )
    assert (
        pick_member(
            [Candidate(1, NOW - timedelta(hours=1)), Candidate(2, NOW - timedelta(days=2))],
            NOW,
            ChooseHeaviest(),
        )
        == 2
    )
    assert (
        pick_member(
            [Candidate(1, NOW - timedelta(hours=1)), Candidate(2, NOW - timedelta(hours=3))],
            NOW,
            ChooseHeaviest(),
        )
        == 2
    )
    assert pick_member([Candidate(1)], NOW) == 1


def test_deadline_extends_out_of_quiet_and_uses_utc():
    assert challenge_deadline(NOW, 2, "Asia/Tashkent", time(23), time(8)) == datetime(
        2026, 11, 8, 3, tzinfo=UTC
    )
    early = NOW.replace(hour=10)
    assert challenge_deadline(early, 2, "Asia/Tashkent", time(23), time(8)) == early + timedelta(
        hours=2
    )


@pytest.mark.parametrize("kind,expected", CHALLENGE_DONE.items())
def test_challenge_points(kind, expected):
    assert challenge_points(kind, done=True) == expected
    assert challenge_points(kind, done=False) == -5
    assert challenge_points(kind, done=False, penalty_mode="off") == 0


@pytest.mark.parametrize(
    "mode,user,misses,expected",
    [
        ("off", 2, 10, False),
        ("points", 2, 10, False),
        ("mute", 2, 1, True),
        ("kick", 2, 2, False),
        ("kick", 2, 3, True),
        ("mute", 1, 1, False),
        ("kick", 7, 10, False),
    ],
)
def test_penalty_policy_protects_admin_owner_and_threshold(mode, user, misses, expected):
    assert should_restrict(mode, user, 1, {7}, misses, 3) == expected


def test_week_start_is_local_monday_converted_to_utc():
    assert week_start(NOW, "Asia/Tashkent") == datetime(2026, 11, 1, 19, tzinfo=UTC)
