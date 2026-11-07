"""Read-only preflight: python scripts/check_env.py. Never prints credentials."""

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot import texts  # noqa: E402

# Missing setup needs no SDK imports or network stack. This also keeps the CLI
# responsive on Windows while antivirus scans a cold Python environment.
if __name__ == "__main__" and not (ROOT / ".env").is_file():
    print(texts.ENV_FILE_MISSING)
    raise SystemExit(1)

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import (  # noqa: E402
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramUnauthorizedError,
)
from pydantic import ValidationError  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from bot.config import Settings  # noqa: E402
from bot.db.models import Base  # noqa: E402
from bot.db.session import create_engine  # noqa: E402


def token_format_valid(token: str) -> bool:
    """Check syntax, not authenticity; getMe is the authority for a real token."""
    return bool(re.fullmatch(r"[1-9][0-9]*:[A-Za-z0-9_-]+", token)) and token != (
        "123456789:replace_with_your_botfather_token"
    )


async def check_telegram(settings, emit=print) -> bool:
    token = settings.bot_token.get_secret_value()
    if not token_format_valid(token):
        emit(texts.ENV_TOKEN_BAD)
        emit(texts.ENV_TELEGRAM_SKIPPED)
        return False
    emit(texts.ENV_TOKEN_OK)
    try:
        async with asyncio.timeout(15), Bot(token=token) as bot:
            identity = await bot.get_me(request_timeout=10)
    except TelegramUnauthorizedError:
        emit(texts.ENV_TOKEN_REJECTED)
        return False
    except TelegramRetryAfter as error:
        emit(texts.env_retry_after(error.retry_after))
        return False
    except TelegramNetworkError:
        emit(texts.ENV_TELEGRAM_NETWORK)
        return False
    except TimeoutError:
        emit(texts.ENV_TELEGRAM_TIMEOUT)
        return False
    except Exception:
        # Exception strings can contain a request URL/token; intentionally do not print them.
        emit(texts.ENV_TELEGRAM_FAILED)
        return False
    emit(texts.ENV_GETME_OK)
    if (identity.username or "").casefold() != settings.bot_username.casefold():
        emit(texts.ENV_USERNAME_BAD)
        return False
    emit(texts.ENV_USERNAME_OK)
    return True


def schema_ready(connection) -> bool:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    return all(
        table.name in tables
        and set(table.columns.keys()).issubset(
            {column["name"] for column in inspector.get_columns(table.name)}
        )
        for table in Base.metadata.tables.values()
    )


async def check_database(settings, root=ROOT, emit=print) -> bool:
    engine = None
    ready = False
    try:
        url = make_url(settings.database_url.get_secret_value())
        if url.drivername == "sqlite+aiosqlite" and url.database != ":memory:":
            # Match the bot's documented project-root working directory, even if this
            # script was launched from elsewhere. Missing SQLite files are not created.
            database = Path(url.database)
            if not database.is_absolute():
                database = root / database
            if not database.is_file():
                emit(texts.ENV_DB_MISSING)
                return False
            url = url.set(database=str(database.resolve()))
        engine = create_engine(
            url.render_as_string(hide_password=False), pool_size=settings.db_pool_size
        )
        async with asyncio.timeout(10), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            emit(texts.ENV_DB_OK)
            ready = await connection.run_sync(schema_ready)
        emit(texts.ENV_SCHEMA_OK if ready else texts.ENV_SCHEMA_BAD)
    except TimeoutError:
        emit(texts.ENV_DB_TIMEOUT)
        ready = False
    except Exception:
        emit(texts.ENV_DB_FAILED)
        ready = False
    finally:
        if engine is not None:
            try:
                async with asyncio.timeout(5):
                    await engine.dispose()
            except Exception:
                emit(texts.ENV_DB_FAILED)
                ready = False
    return ready


async def check_environment(root=ROOT, emit=print) -> int:
    if not (root / ".env").is_file():
        emit(texts.ENV_FILE_MISSING)
        return 1
    try:
        settings = Settings(_env_file=root / ".env")
    except ValidationError as error:
        emit(texts.ENV_INVALID_HEADER)
        for problem in error.errors(include_url=False, include_context=False, include_input=False):
            field = problem["loc"][0] if problem["loc"] else None
            emit("  - " + texts.ENV_FIELD_HINTS.get(field, texts.ENV_RUNTIME_HINT))
        return 1
    except Exception:
        emit(texts.ENV_FILE_UNREADABLE)
        return 1
    emit(texts.ENV_SETTINGS_OK)
    # Run both independent probes, so a Telegram error does not hide a DB problem.
    telegram_ok = await check_telegram(settings, emit)
    database_ok = await check_database(settings, root, emit)
    emit(texts.ENV_CHECK_OK if telegram_ok and database_ok else texts.ENV_CHECK_FAILED)
    return 0 if telegram_ok and database_ok else 1


def main() -> None:
    try:
        code = asyncio.run(check_environment())
    except KeyboardInterrupt:
        print(texts.ENV_CHECK_CANCELLED)
        code = 130
    except Exception:
        print(texts.ENV_CHECK_FAILED)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
