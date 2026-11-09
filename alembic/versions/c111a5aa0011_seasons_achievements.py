"""Monthly due schedule and idempotent achievement unlocks.

Revision ID: c111a5aa0011
Revises: c106a5aa0010
"""

import hashlib
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "c111a5aa0011"
down_revision = "c106a5aa0010"
branch_labels = depends_on = None


def upgrade():
    op.add_column("chats", sa.Column("next_season_at", sa.DateTime(timezone=True)))
    op.create_index("ix_chats_next_season_at", "chats", ["next_season_at"])
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.drop_constraint(op.f("ck_scheduled_posts_kind"), type_="check")
        batch.create_check_constraint(
            op.f("ck_scheduled_posts_kind"), "kind IN ('daily', 'weekly', 'season')"
        )
    op.create_table(
        "achievements",
        sa.Column("chat_id", sa.BigInteger(), sa.ForeignKey("chats.id"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("announced_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_achievements_unclaimed", "achievements", ["claimed_at", "unlocked_at"])
    op.create_index("ix_achievements_user_id", "achievements", ["user_id"])
    # Only this migration backfills old chats. Runtime ticks never enumerate them.
    table = sa.table(
        "chats",
        sa.column("id", sa.BigInteger()),
        sa.column("tz", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("bot_is_admin", sa.Boolean()),
        sa.column("next_season_at", sa.DateTime(timezone=True)),
    )
    connection, last, now = op.get_bind(), None, datetime.now(UTC)
    while True:
        query = sa.select(table.c.id, table.c.tz).where(
            table.c.is_active.is_(True), table.c.bot_is_admin.is_(True)
        )
        if last is not None:
            query = query.where(table.c.id > last)
        rows = connection.execute(query.order_by(table.c.id).limit(500)).all()
        if not rows:
            break
        for row in rows:
            local = now.astimezone(ZoneInfo(row.tz))
            year, month = (
                (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
            )
            from datetime import timedelta

            offset = (
                int.from_bytes(
                    hashlib.blake2b(f"oqibat:season:{row.id}".encode(), digest_size=8).digest(),
                    "big",
                )
                % 901
            )
            due = (
                datetime(year, month, 1, 9, tzinfo=ZoneInfo(row.tz)) + timedelta(seconds=offset)
            ).astimezone(UTC)
            connection.execute(
                table.update().where(table.c.id == row.id).values(next_season_at=due)
            )
        last = rows[-1].id


def downgrade():
    op.drop_table("achievements")
    op.execute("DELETE FROM scheduled_posts WHERE kind = 'season'")
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.drop_constraint(op.f("ck_scheduled_posts_kind"), type_="check")
        batch.create_check_constraint(
            op.f("ck_scheduled_posts_kind"), "kind IN ('daily', 'weekly')"
        )
    with op.batch_alter_table("chats") as batch:
        batch.drop_index("ix_chats_next_season_at")
        batch.drop_column("next_season_at")
