"""Pure weighted participant selection."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Candidate:
    user_id: int
    last_picked_at: datetime | None = None
    opted_in: bool = True
    active: bool = True
    pending: bool = False


def pick_member(candidates: list[Candidate], now: datetime, rng=None) -> int | None:
    eligible = [item for item in candidates if item.opted_in and item.active and not item.pending]
    if not eligible:
        return None
    rested = [
        item
        for item in eligible
        if item.last_picked_at is None or item.last_picked_at <= now - timedelta(hours=24)
    ]
    pool = rested or eligible
    weights = [
        max(1, (now - item.last_picked_at).total_seconds()) if item.last_picked_at else 7 * 86400
        for item in pool
    ]
    return (rng or random).choices([item.user_id for item in pool], weights=weights, k=1)[0]
