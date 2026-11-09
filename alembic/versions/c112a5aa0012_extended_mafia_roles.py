"""Opt-in extended Mafia role layout, disabled by default.

Revision ID: c112a5aa0012
Revises: c111a5aa0011
"""

import sqlalchemy as sa
from alembic import op

revision = "c112a5aa0012"
down_revision = "c111a5aa0011"
branch_labels = depends_on = None


def upgrade():
    op.add_column(
        "chats",
        sa.Column("extended_roles", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    with op.batch_alter_table("chats") as batch:
        batch.drop_column("extended_roles")
