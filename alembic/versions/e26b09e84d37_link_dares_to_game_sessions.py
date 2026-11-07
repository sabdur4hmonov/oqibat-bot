"""Link dare tasks to their game for atomic completion, expiry and refusal.

Revision ID: e26b09e84d37
Revises: 31b65b0e9d42
"""

import sqlalchemy as sa
from alembic import op

revision = "e26b09e84d37"
down_revision = "31b65b0e9d42"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("challenges") as batch:
        batch.add_column(sa.Column("game_session_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_challenges_game_session_id_game_sessions"),
            "game_sessions",
            ["game_session_id"],
            ["id"],
        )
        batch.create_index(op.f("ix_challenges_game_session_id"), ["game_session_id"])


def downgrade():
    with op.batch_alter_table("challenges") as batch:
        batch.drop_index(op.f("ix_challenges_game_session_id"))
        batch.drop_constraint(
            op.f("fk_challenges_game_session_id_game_sessions"), type_="foreignkey"
        )
        batch.drop_column("game_session_id")
