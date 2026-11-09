"""Approved bounded announcement recovery on existing rows.

Revision ID: c106a5aa0010
Revises: b45a921b3120
"""

import sqlalchemy as sa
from alembic import op

revision = "c106a5aa0010"
down_revision = "b45a921b3120"
branch_labels = depends_on = None


def upgrade():
    op.add_column("challenges", sa.Column("announce_retry_at", sa.DateTime(timezone=True)))
    op.create_index("ix_challenges_announce_retry_at", "challenges", ["announce_retry_at"])
    op.create_index("ix_game_sessions_created_at", "game_sessions", ["created_at"])
    for name in (
        "assigned_announced_at",
        "result_announced_at",
        "assigned_skipped_at",
        "result_skipped_at",
    ):
        op.add_column("challenges", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_challenges_assignment_recovery",
        "challenges",
        ["assigned_announced_at", "assigned_skipped_at", "created_at"],
    )
    op.create_index(
        "ix_challenges_result_recovery",
        "challenges",
        ["result_announced_at", "result_skipped_at", "resolved_at"],
    )
    op.execute(
        "UPDATE challenges SET assigned_announced_at = created_at WHERE message_id IS NOT NULL"
    )
    # Historical final rows predate the feature: never replay all past successes.
    op.execute("UPDATE challenges SET result_skipped_at = resolved_at WHERE status != 'pending'")
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_scheduled_posts_retry_at", ["retry_at"])
    from datetime import UTC, datetime, timedelta

    # Pre-feature unsent posts have no reliable claim timestamp: never revive historical spam.
    statement = sa.text(
        "UPDATE scheduled_posts SET claimed_at = COALESCE(posted_at, :old), sent_at = posted_at"
    ).bindparams(sa.bindparam("old", type_=sa.DateTime(timezone=True)))
    op.get_bind().execute(statement, {"old": datetime.now(UTC) - timedelta(hours=7)})
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.alter_column("claimed_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_index("ix_scheduled_posts_claimed_at", ["claimed_at"])
        batch.create_index("ix_scheduled_posts_sent_at", ["sent_at"])


def downgrade():
    op.drop_index("ix_challenges_announce_retry_at", table_name="challenges")
    op.drop_index("ix_game_sessions_created_at", table_name="game_sessions")
    with op.batch_alter_table("scheduled_posts") as batch:
        batch.drop_index("ix_scheduled_posts_retry_at")
        batch.drop_column("retry_at")
        batch.drop_index("ix_scheduled_posts_sent_at")
        batch.drop_index("ix_scheduled_posts_claimed_at")
        batch.drop_column("sent_at")
        batch.drop_column("claimed_at")
    op.drop_index("ix_challenges_assignment_recovery", table_name="challenges")
    op.drop_index("ix_challenges_result_recovery", table_name="challenges")
    with op.batch_alter_table("challenges") as batch:
        batch.drop_column("announce_retry_at")
        for name in (
            "assigned_announced_at",
            "result_announced_at",
            "assigned_skipped_at",
            "result_skipped_at",
        ):
            batch.drop_column(name)
