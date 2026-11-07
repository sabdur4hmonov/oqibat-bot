"""Track would-you-rather polls as stoppable game sessions.

Revision ID: 31b65b0e9d42
Revises: 7d9a7f721c61
"""

from alembic import op

revision = "31b65b0e9d42"
down_revision = "7d9a7f721c61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(
            op.f("ck_game_sessions_game"),
            "game IN ('quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia')",
        )


def downgrade() -> None:
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(
            op.f("ck_game_sessions_game"), "game IN ('quiz', 'duel', 'krokodil', 'hyj', 'mafia')"
        )
