"""Persist per-chat owner-only test mode; existing production chats stay normal."""

import sqlalchemy as sa
from alembic import op

revision = "c126a5aa0026"
down_revision = "c121a5aa0021"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "chats", sa.Column("fast_mode", sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade():
    with op.batch_alter_table("chats") as batch:
        batch.drop_column("fast_mode")
