"""Allow rock-paper-scissors in the existing game session ledger.

Revision ID: c115a5aa0015
Revises: c113a5aa0013
"""

from alembic import op

revision = "c115a5aa0015"
down_revision = "c113a5aa0013"
branch_labels = None
depends_on = None


def constraint(games):
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({games})")


def upgrade():
    constraint("'quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia', 'rps'")


def downgrade():
    # Refuse a lossy downgrade when new-type rows exist. The owner must retain
    # their history, not silently delete it to satisfy the old CHECK constraint.
    if (
        op.get_bind()
        .exec_driver_sql("SELECT 1 FROM game_sessions WHERE game = 'rps' LIMIT 1")
        .first()
    ):
        raise RuntimeError("Cannot downgrade while rps game history exists")
    constraint("'quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia'")
