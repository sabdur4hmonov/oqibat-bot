"""Allow bounded number hunt and arithmetic matches in the shared session table.

Revision ID: c116a5aa0016
Revises: c115a5aa0015
"""

from alembic import op

revision = "c116a5aa0016"
down_revision = "c115a5aa0015"
branch_labels = None
depends_on = None


def constraint(games):
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({games})")


def upgrade():
    constraint("'quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia', 'rps', 'number', 'math'")


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT 1 FROM game_sessions WHERE game IN ('number','math') LIMIT 1")
        .first()
    ):
        raise RuntimeError("Cannot downgrade while number/math game history exists")
    constraint("'quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia', 'rps'")
