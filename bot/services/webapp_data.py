"""Explicit read-only projections; no game JSON or private role state is exposed."""

from sqlalchemy import func, select

from bot import texts
from bot.db.models import Achievement, Chat, Membership, PointEvent, User
from bot.services.levels import group_totals, level_for
from bot.services.seasons import month_bounds
from bot.utils.time import utc_now


async def profile(sessions, identity):
    async with sessions() as session:
        user = await session.get(User, identity.user_id)
        points = await session.scalar(
            select(func.coalesce(func.sum(PointEvent.delta), 0)).where(
                PointEvent.user_id == identity.user_id
            )
        )
        achievements = await session.scalar(
            select(func.count(func.distinct(Achievement.key)))
            .select_from(Achievement)
            .where(Achievement.user_id == identity.user_id)
        )
        unlocked_rows = (
            await session.execute(
                select(Achievement.key, func.min(Achievement.unlocked_at))
                .where(Achievement.user_id == identity.user_id)
                .group_by(Achievement.key)
            )
        ).all()
        unlocked = {key: at.isoformat() for key, at in unlocked_rows}
        groups = (
            await session.execute(
                select(Chat.id, Chat.title, Chat.tz, Membership.opted_in)
                .join(Membership)
                .where(
                    Membership.user_id == identity.user_id,
                    Membership.is_active.is_(True),
                    Chat.is_active.is_(True),
                    Chat.id < 0,
                )
                .order_by(Chat.title, Chat.id)
                .limit(500)
            )
        ).all()
    return {
        "id": identity.user_id,
        "name": user.first_name if user else identity.first_name,
        "username": user.username if user else identity.username,
        "points": points,
        "achievements": achievements,
        "level": level_for(points),
        "season_ends_at": month_bounds(utc_now(), "Asia/Tashkent")[1].isoformat(),
        "gallery": [
            {"key": key, "label": label, "unlocked_at": unlocked.get(key)}
            for key, label in texts.ACHIEVEMENTS.items()
        ],
        "groups": [
            {"id": row.id, "title": row.title, "tz": row.tz, "opted_in": row.opted_in}
            for row in groups
        ],
    }


async def leaderboard(runtime, chat, scope):
    since, until = month_bounds(utc_now(), chat.tz)
    rows = await runtime.points.top(
        chat.id, since if scope == "season" else None, until if scope == "season" else None
    )
    from zoneinfo import ZoneInfo

    totals = await group_totals(runtime.sessions, chat.id, [row[0] for row in rows])

    return {
        "group": {"id": chat.id, "title": chat.title, "tz": chat.tz},
        "scope": scope,
        "label": texts.season_month(since.astimezone(ZoneInfo(chat.tz)).date())
        if scope == "season"
        else texts.WEB_COPY["all_time"],
        "season_ends_at": until.isoformat(),
        "items": [
            {"id": user, "name": name, "points": points, "level": level_for(totals.get(user, 0))}
            for user, name, points in rows
        ],
    }


async def achievements(sessions, chat, user):
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(Achievement).where(
                    Achievement.chat_id == chat.id, Achievement.user_id == user
                )
            )
        ).all()
    unlocked = {row.key: row.unlocked_at.isoformat() for row in rows}
    return {
        "group": {"id": chat.id, "title": chat.title, "tz": chat.tz},
        "season_ends_at": month_bounds(utc_now(), chat.tz)[1].isoformat(),
        "items": [
            {"key": key, "label": label, "unlocked_at": unlocked.get(key)}
            for key, label in texts.ACHIEVEMENTS.items()
        ],
    }
