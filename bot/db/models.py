"""Initial schema from PLAN section 5. Schema updates require new migrations."""

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Time,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from bot.utils.time import utc_now


class UTCDateTime(TypeDecorator[datetime]):
    """Reject naive datetimes; restore UTC awareness when SQLite drops tzinfo."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Persisted timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class Chat(Timestamps, Base):
    __tablename__ = "chats"
    __table_args__ = (
        CheckConstraint("challenges_per_day BETWEEN 0 AND 3", name="challenge_count"),
        CheckConstraint("challenge_hours IN (2, 6, 10, 24)", name="challenge_hours"),
        CheckConstraint("penalty_mode IN ('off', 'points', 'mute', 'kick')", name="penalty_mode"),
        CheckConstraint("mute_days IN (1, 3, 7)", name="mute_days"),
        CheckConstraint("kick_after_misses > 0", name="kick_after_misses"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bot_is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    tz: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_time: Mapped[time] = mapped_column(Time, default=time(9))
    challenges_per_day: Mapped[int] = mapped_column(Integer, default=1)
    challenge_hours: Mapped[int] = mapped_column(Integer, default=10)
    penalty_mode: Mapped[str] = mapped_column(String(10), default="points")
    mute_days: Mapped[int] = mapped_column(Integer, default=3)
    kick_after_misses: Mapped[int] = mapped_column(Integer, default=3)
    quiet_start: Mapped[time] = mapped_column(Time, default=time(23))
    quiet_end: Mapped[time] = mapped_column(Time, default=time(8))
    next_daily_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    next_challenge_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    next_weekly_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)


class User(Timestamps, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(32))
    started_private: Mapped[bool] = mapped_column(Boolean, default=False)


class Membership(Base):
    __tablename__ = "memberships"
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_in_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_picked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    consecutive_misses: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PointEvent(Base):
    __tablename__ = "point_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))
    ref_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (
        CheckConstraint("kind IN ('video_note', 'voice', 'photo', 'text')", name="kind"),
        CheckConstraint("status IN ('pending', 'done', 'missed', 'cancelled')", name="status"),
        Index("ix_challenges_status_deadline", "status", "deadline_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(16))
    prompt_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    deadline_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ContentUsage(Base):
    __tablename__ = "content_usage"
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    content_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    used_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (CheckConstraint("kind IN ('daily', 'weekly')", name="kind"),)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)


class GameSession(Timestamps, Base):
    __tablename__ = "game_sessions"
    __table_args__ = (
        CheckConstraint("game IN ('quiz', 'duel', 'krokodil', 'hyj', 'mafia')", name="game"),
        CheckConstraint("status IN ('lobby', 'running', 'finished', 'cancelled')", name="status"),
        Index("ix_game_sessions_status_deadline", "status", "phase_deadline_at"),
        Index(
            "uq_game_sessions_active_chat",
            "chat_id",
            unique=True,
            sqlite_where=text("game != 'duel' AND status IN ('lobby', 'running')"),
            postgresql_where=text("game != 'duel' AND status IN ('lobby', 'running')"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id"), index=True)
    game: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="lobby")
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    phase_deadline_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
