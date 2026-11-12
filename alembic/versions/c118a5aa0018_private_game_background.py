"""Secret missions have an independent background slot."""

import sqlalchemy as sa
from alembic import op

revision = "c118a5aa0018"
down_revision = "c116a5aa0016"
branch_labels = depends_on = None
OLD = "'quiz', 'duel', 'wyr', 'krokodil', 'hyj', 'mafia', 'rps', 'number', 'math'"


def upgrade():
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({OLD}, 'secret')")
        batch.drop_index("uq_game_sessions_active_chat")
        batch.create_index(
            "uq_game_sessions_active_chat",
            ["chat_id"],
            unique=True,
            sqlite_where=sa.text("game NOT IN ('duel','secret') AND status IN ('lobby','running')"),
            postgresql_where=sa.text(
                "game NOT IN ('duel','secret') AND status IN ('lobby','running')"
            ),
        )
        batch.create_index(
            "uq_game_sessions_background_chat",
            ["chat_id"],
            unique=True,
            sqlite_where=sa.text("game = 'secret' AND status IN ('lobby','running')"),
            postgresql_where=sa.text("game = 'secret' AND status IN ('lobby','running')"),
        )


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql("SELECT 1 FROM game_sessions WHERE game='secret' LIMIT 1")
        .first()
    ):
        raise RuntimeError("Cannot remove secret game history")
    with op.batch_alter_table("game_sessions") as batch:
        batch.drop_index("uq_game_sessions_background_chat")
        batch.drop_index("uq_game_sessions_active_chat")
        batch.create_index(
            "uq_game_sessions_active_chat",
            ["chat_id"],
            unique=True,
            sqlite_where=sa.text("game != 'duel' AND status IN ('lobby','running')"),
            postgresql_where=sa.text("game != 'duel' AND status IN ('lobby','running')"),
        )
        batch.drop_constraint(op.f("ck_game_sessions_game"), type_="check")
        batch.create_check_constraint(op.f("ck_game_sessions_game"), f"game IN ({OLD})")
