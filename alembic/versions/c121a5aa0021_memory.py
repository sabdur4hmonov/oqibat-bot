"""Allow consented private-photo guessing sessions."""

from alembic import op

revision = "c121a5aa0021"
down_revision = "c120a5aa0020"
branch_labels = depends_on = None
OLD = (
    "'quiz','duel','wyr','krokodil','hyj','mafia','rps','number','math','secret','kim','telephone'"
)


def constraint(values):
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({values})")


def upgrade():
    constraint(OLD + ",'memory'")


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT 1 FROM game_sessions WHERE game='memory' LIMIT 1")
        .first()
    ):
        raise RuntimeError("Cannot remove memory game history")
    constraint(OLD)
