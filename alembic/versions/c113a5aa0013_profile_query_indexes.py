"""Index known-own-group lookup and owner daily activity aggregates.

Revision ID: c113a5aa0013
Revises: c112a5aa0012
"""
from alembic import op

revision = "c113a5aa0013"
down_revision = "c112a5aa0012"
branch_labels = depends_on = None


def upgrade():
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.create_index("ix_memberships_last_seen_at", "memberships", ["last_seen_at"])


def downgrade():
    op.drop_index("ix_memberships_last_seen_at", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
