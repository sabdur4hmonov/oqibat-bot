"""Allow anonymous-answer games without changing existing history."""

from alembic import op

revision = "c119a5aa0019"
down_revision = "c118a5aa0018"
branch_labels = depends_on = None
OLD = "'quiz','duel','wyr','krokodil','hyj','mafia','rps','number','math','secret'"


def constraint(values):
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({values})")


def upgrade():
    constraint(OLD + ",'kim'")


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT 1 FROM game_sessions WHERE game='kim' LIMIT 1")
        .first()
    ):
        raise RuntimeError("Cannot remove Kim aytdi history")
    constraint(OLD)
