import sqlite3

from test_rps_migration import migrate, seeded_previous


async def test_populated_head_keeps_history_and_defaults_fast_mode_off(tmp_path):
    path = tmp_path / "fast.db"
    url = await seeded_previous(path)
    result = await migrate(url, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT fast_mode FROM chats WHERE id=-1").fetchone() == (0,)
        connection.execute("UPDATE chats SET fast_mode=1 WHERE id=-1")
        connection.commit()
        ids = connection.execute("SELECT id FROM game_sessions ORDER BY id").fetchall()
        ledger = connection.execute("SELECT id,delta FROM point_events").fetchall()
    result = await migrate(url, "downgrade", "c121a5aa0021")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as connection:
        assert "fast_mode" not in {row[1] for row in connection.execute("PRAGMA table_info(chats)")}
        assert connection.execute("SELECT id FROM game_sessions ORDER BY id").fetchall() == ids
        assert connection.execute("SELECT id,delta FROM point_events").fetchall() == ledger
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
