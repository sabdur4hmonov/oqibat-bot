"""Pure passive levels plus one bounded all-time ledger projection."""

from bisect import bisect_right

from sqlalchemy import func, select

from bot import texts
from bot.constants import LEVEL_THRESHOLDS
from bot.db.models import PointEvent


def level_for(points):
    index = max(0, bisect_right(LEVEL_THRESHOLDS, points) - 1)
    start = LEVEL_THRESHOLDS[index]
    end = LEVEL_THRESHOLDS[index + 1] if index + 1 < len(LEVEL_THRESHOLDS) else None
    return {
        "number": index + 1,
        "title": texts.LEVEL_TITLES[index],
        "next_threshold": end,
        "remaining": max(0, end - points) if end else 0,
        "progress": max(0, min(100, (points - start) * 100 // (end - start))) if end else 100,
    }


async def group_totals(sessions, chat_id, users):
    if not users or chat_id is None:
        return {}
    async with sessions() as session:
        rows = (
            await session.execute(
                select(PointEvent.user_id, func.sum(PointEvent.delta))
                .where(PointEvent.chat_id == chat_id, PointEvent.user_id.in_(users))
                .group_by(PointEvent.user_id)
            )
        ).all()
    return dict(rows)
