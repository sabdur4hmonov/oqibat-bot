"""Pure test-mode policy; production deadlines pass through bit-for-bit unchanged."""

from datetime import datetime

CLOCK_FIELDS = ("end_at", "answer_until", "hard_deadline")


def scale_at(at, base, factor):
    if factor == 1:
        return at
    return base + (at - base) * factor if at is not None and at > base else at


def scale_times(row, previous, previous_deadline, base):
    factor = previous.get("timer_multiplier", row.state.get("timer_multiplier", 1))
    if factor == 1:
        return
    row.state["timer_multiplier"] = factor
    known = {previous_deadline} if previous_deadline else set()
    for key in CLOCK_FIELDS:
        if previous.get(key):
            known.add(datetime.fromisoformat(previous[key]))
    mapped = {}

    def scaled(at):
        if at is None or at in known:
            return at
        if at not in mapped:
            mapped[at] = scale_at(at, base, factor)
        return mapped[at]

    for key in CLOCK_FIELDS:
        if row.state.get(key) and row.state[key] != previous.get(key):
            row.state[key] = scaled(datetime.fromisoformat(row.state[key])).isoformat()
    row.phase_deadline_at = scaled(row.phase_deadline_at)
    if row.game == "secret":
        for user, until in row.state.get("cooldowns", {}).items():
            if until != previous.get("cooldowns", {}).get(user) and until > base.timestamp():
                row.state["cooldowns"][user] = (
                    base.timestamp() + (until - base.timestamp()) * factor
                )
