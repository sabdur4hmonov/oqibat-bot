import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import pytest_asyncio

from bot.config import Settings
from bot.db.session import create_engine, create_session_factory

ROOT = Path(__file__).resolve().parents[1]
TEST_TOKEN = "123456789:local_test_token_never_used_on_telegram"


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        bot_token=TEST_TOKEN,
        bot_username="OqibatBot",
        instagram_handle="oqibat.test",
        owner_id=123,
    )


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory):
    path = tmp_path_factory.mktemp("schema") / "template.db"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=os.environ | {"DATABASE_URL": url},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return path


@pytest.fixture
def database_url(migrated_template, tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_template, path)
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest_asyncio.fixture
async def sessions(database_url):
    engine = create_engine(database_url)
    try:
        yield create_session_factory(engine)
    finally:
        await engine.dispose()
