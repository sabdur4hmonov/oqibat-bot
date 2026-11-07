import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter, TelegramUnauthorizedError
from aiogram.methods import GetMe
from pydantic import SecretStr

from bot import texts
from bot.config import Settings
from scripts import check_env

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "123456789:local_test_token_never_used_on_telegram"


@pytest.mark.parametrize("token", [TOKEN, "9:abc_DEF-123"])
def test_accepts_token_syntax_without_claiming_authenticity(token):
    assert check_env.token_format_valid(token)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "bad",
        "abc:def",
        "0:abc",
        "-1:abc",
        "123:",
        "123:abc:def",
        "123:has space",
        "123:слово",
        "123:secret\n",
        "123456789:replace_with_your_botfather_token",
    ],
)
def test_rejects_bad_token_syntax_and_example_placeholder(token):
    assert not check_env.token_format_valid(token)


def fake_bot(username="OqibatBot", error=None):
    bot = MagicMock()
    bot.__aenter__ = AsyncMock(return_value=bot)
    bot.__aexit__ = AsyncMock(return_value=False)
    bot.get_me = AsyncMock(return_value=SimpleNamespace(username=username), side_effect=error)
    return bot


async def test_getme_authentication_username_and_session_cleanup(settings):
    output = []
    bot = fake_bot("oqibatbot")
    with patch.object(check_env, "Bot", return_value=bot):
        assert await check_env.check_telegram(settings, output.append)
    assert texts.ENV_GETME_OK in output and texts.ENV_USERNAME_OK in output
    bot.get_me.assert_awaited_once_with(request_timeout=10)
    bot.__aexit__.assert_awaited_once()
    assert settings.bot_token.get_secret_value() not in "\n".join(output)


async def test_username_mismatch_is_reported_without_claiming_success(settings):
    output = []
    with patch.object(check_env, "Bot", return_value=fake_bot("AnotherBot")):
        assert not await check_env.check_telegram(settings, output.append)
    assert texts.ENV_GETME_OK in output and texts.ENV_USERNAME_BAD in output
    assert texts.ENV_USERNAME_OK not in output


@pytest.mark.parametrize(
    "error,expected",
    [
        (TelegramUnauthorizedError(GetMe(), TOKEN), texts.ENV_TOKEN_REJECTED),
        (TelegramNetworkError(GetMe(), TOKEN), texts.ENV_TELEGRAM_NETWORK),
        (TimeoutError(TOKEN), texts.ENV_TELEGRAM_TIMEOUT),
        (TelegramRetryAfter(GetMe(), TOKEN, retry_after=7), texts.env_retry_after(7)),
        (RuntimeError(TOKEN), texts.ENV_TELEGRAM_FAILED),
    ],
)
async def test_telegram_errors_are_actionable_and_do_not_expose_token(settings, error, expected):
    output = []
    bot = fake_bot(error=error)
    with patch.object(check_env, "Bot", return_value=bot):
        assert not await check_env.check_telegram(settings, output.append)
    assert expected in output
    assert TOKEN not in "\n".join(output)
    bot.__aexit__.assert_awaited_once()


async def test_placeholder_never_makes_a_telegram_request(settings):
    output = []
    settings = settings.model_copy(
        update={"bot_token": SecretStr("123456789:replace_with_your_botfather_token")}
    )
    with patch.object(check_env, "Bot") as constructor:
        assert not await check_env.check_telegram(settings, output.append)
    constructor.assert_not_called()
    assert texts.ENV_TOKEN_BAD in output


async def test_real_database_probe_checks_migrated_schema(database_url, settings, tmp_path):
    output = []
    settings = settings.model_copy(update={"database_url": SecretStr(database_url)})
    assert await check_env.check_database(settings, tmp_path, output.append)
    assert output == [texts.ENV_DB_OK, texts.ENV_SCHEMA_OK]


async def test_relative_sqlite_path_uses_project_root_not_shell_directory(
    database_url, settings, tmp_path, monkeypatch
):
    output = []
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    settings = settings.model_copy(
        update={"database_url": SecretStr("sqlite+aiosqlite:///./test.db")}
    )
    assert await check_env.check_database(settings, tmp_path, output.append)
    assert not (elsewhere / "test.db").exists()


async def test_missing_sqlite_is_not_created_and_empty_db_is_reported(settings, tmp_path):
    output = []
    settings = settings.model_copy(
        update={"database_url": SecretStr("sqlite+aiosqlite:///./empty.db")}
    )
    assert not await check_env.check_database(settings, tmp_path, output.append)
    assert output == [texts.ENV_DB_MISSING]
    assert not (tmp_path / "empty.db").exists()
    (tmp_path / "empty.db").touch()
    output.clear()
    assert not await check_env.check_database(settings, tmp_path, output.append)
    assert output == [texts.ENV_DB_OK, texts.ENV_SCHEMA_BAD]
    assert (tmp_path / "empty.db").stat().st_size == 0


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            RuntimeError("postgresql+asyncpg://user:private_password@localhost/db"),
            texts.ENV_DB_FAILED,
        ),
        (TimeoutError("private_password"), texts.ENV_DB_TIMEOUT),
    ],
)
async def test_database_failures_close_pool_and_hide_connection_details(
    settings, tmp_path, error, expected
):
    output = []
    settings = settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+asyncpg://user:private_password@localhost/db")
        }
    )
    engine = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=error)
    context.__aexit__ = AsyncMock(return_value=False)
    engine.connect.return_value = context
    engine.dispose = AsyncMock()
    with patch.object(check_env, "create_engine", return_value=engine):
        assert not await check_env.check_database(settings, tmp_path, output.append)
    engine.dispose.assert_awaited_once()
    assert expected in output and "private_password" not in "\n".join(output)


def write_env(path, database_url):
    (path / ".env").write_text(
        f"BOT_TOKEN={TOKEN}\nBOT_USERNAME=OqibatBot\nOWNER_ID=123\n"
        f"INSTAGRAM_HANDLE=oqibat.test\nDATABASE_URL={database_url}\n"
        "ENVIRONMENT=development\nUSE_WEBHOOK=false\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def clear_config_environment(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


async def test_missing_env_reports_setup_without_network(tmp_path):
    output = []
    with patch.object(check_env, "Bot") as bot:
        assert await check_env.check_environment(tmp_path, output.append) == 1
    bot.assert_not_called()
    assert output == [texts.ENV_FILE_MISSING]


async def test_invalid_env_reports_all_fields_without_values_or_traceback(tmp_path):
    output = []
    (tmp_path / ".env").write_text(
        "BOT_TOKEN=PRIVATE_SECRET\nBOT_USERNAME=bad\nOWNER_ID=0\n", encoding="utf-8"
    )
    assert await check_env.check_environment(tmp_path, output.append) == 1
    messages = "\n".join(output)
    assert all(
        field in messages for field in ("BOT_TOKEN", "BOT_USERNAME", "OWNER_ID", "INSTAGRAM_HANDLE")
    )
    assert "PRIVATE_SECRET" not in messages and "Traceback" not in messages


async def test_bad_model_configuration_gives_local_setup_hint(tmp_path):
    output = []
    write_env(tmp_path, "sqlite+aiosqlite:///./test.db")
    with (tmp_path / ".env").open("a", encoding="utf-8") as file:
        file.write("ENVIRONMENT=production\n")
    assert await check_env.check_environment(tmp_path, output.append) == 1
    assert texts.ENV_RUNTIME_HINT in "\n".join(output)


async def test_full_checker_success_and_telegram_failure_still_checks_db(
    database_url, settings, tmp_path
):
    output = []
    write_env(tmp_path, database_url)
    with patch.object(check_env, "Bot", return_value=fake_bot()):
        assert await check_env.check_environment(tmp_path, output.append) == 0
    assert output[-1] == texts.ENV_CHECK_OK
    output.clear()
    with patch.object(check_env, "Bot", return_value=fake_bot(error=RuntimeError(TOKEN))):
        assert await check_env.check_environment(tmp_path, output.append) == 1
    assert texts.ENV_DB_OK in output and output[-1] == texts.ENV_CHECK_FAILED


def test_cli_main_exit_codes_and_unexpected_errors_do_not_print_secrets(capsys):
    with patch.object(check_env, "check_environment", new=AsyncMock(return_value=0)):
        with pytest.raises(SystemExit) as exit_result:
            check_env.main()
    assert exit_result.value.code == 0
    with patch.object(
        check_env, "check_environment", new=AsyncMock(side_effect=RuntimeError(TOKEN))
    ):
        with pytest.raises(SystemExit) as exit_result:
            check_env.main()
    assert exit_result.value.code == 1
    assert TOKEN not in capsys.readouterr().out


def test_script_launches_from_other_directory_with_missing_env(tmp_path):
    # Execute an isolated script copy to test import/path bootstrapping and failure exit.
    script_dir = tmp_path / "project" / "scripts"
    script_dir.mkdir(parents=True)
    script = script_dir / "check_env.py"
    script.write_text(
        (ROOT / "scripts" / "check_env.py").read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=os.environ | {"PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert result.returncode == 1
    assert texts.ENV_FILE_MISSING in result.stdout and "Traceback" not in result.stderr
