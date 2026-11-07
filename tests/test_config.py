import pytest
from pydantic import ValidationError

from bot.config import DEFAULT_TIMEZONE, DatabaseSettings, Settings


def values():
    return dict(
        bot_token="123456789:local_test_token",
        bot_username="@OqibatBot",
        instagram_handle="@oqibat.test",
        owner_id=123,
    )


def test_loads_env_utf8_and_normalizes_handles(tmp_path, monkeypatch):
    for key in (
        "BOT_TOKEN",
        "BOT_USERNAME",
        "DATABASE_URL",
        "INSTAGRAM_HANDLE",
        "LOG_LEVEL",
        "OWNER_ID",
    ):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=123456789:local_test_token\nBOT_USERNAME=@OqibatBot\n"
        "INSTAGRAM_HANDLE=@oqibat.test\nOWNER_ID=123\nLOG_LEVEL=debug\n",
        encoding="utf-8",
    )
    config = Settings(_env_file=env_file)
    assert config.bot_username == "OqibatBot"
    assert config.instagram_handle == "oqibat.test"
    assert config.log_level == "DEBUG"
    assert DEFAULT_TIMEZONE.key == "Asia/Tashkent"


@pytest.mark.parametrize(
    "field,value",
    [
        ("bot_token", "bad-secret"),
        ("bot_username", "bad/name"),
        ("bot_username", "not_a_username"),
        ("instagram_handle", "<b>bad</b>"),
        ("owner_id", 0),
        ("log_level", "VERBOSE"),
        ("database_url", "sqlite:///sync.db"),
        ("database_url", "not-a-url"),
        ("database_url", "postgresql+asyncpg://localhost"),
    ],
)
def test_rejects_invalid_configuration(field, value):
    data = values() | {field: value}
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **data)
    assert "bad-secret" not in str(error.value)


def test_secrets_are_hidden():
    config = Settings(
        _env_file=None, **values(), database_url="postgresql+asyncpg://me:secret@localhost/db"
    )
    assert "local_test_token" not in repr(config)
    assert "me:secret" not in repr(config)


def test_migrations_do_not_need_a_token(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    config = DatabaseSettings(_env_file=None)
    assert config.database_url.get_secret_value().startswith("sqlite+aiosqlite:")
