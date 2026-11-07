"""Optional, off-by-default dead-player message deletion.

Revision ID: ea783b4100c2
Revises: e26b09e84d37
"""

import sqlalchemy as sa
from alembic import op

revision = "ea783b4100c2"
down_revision = "e26b09e84d37"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chats",
        sa.Column(
            "mafia_delete_dead_messages", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade():
    op.drop_column("chats", "mafia_delete_dead_messages")
