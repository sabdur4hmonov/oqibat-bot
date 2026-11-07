"""Bound weekly reporting to a chat and date window.

Revision ID: b45a921b3120
Revises: ea783b4100c2
"""

from alembic import op

revision = "b45a921b3120"
down_revision = "ea783b4100c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_point_events_chat_created", "point_events", ["chat_id", "created_at"])
    op.create_index("ix_challenges_chat_resolved", "challenges", ["chat_id", "resolved_at"])


def downgrade():
    op.drop_index("ix_challenges_chat_resolved", table_name="challenges")
    op.drop_index("ix_point_events_chat_created", table_name="point_events")
