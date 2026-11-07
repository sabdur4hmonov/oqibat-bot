"""Validated environment configuration; credentials never appear in repr/errors."""

import re
from typing import Literal
from zoneinfo import ZoneInfo

from aiogram.utils.token import TokenValidationError, validate_token
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr = SecretStr("sqlite+aiosqlite:///./oqibat.db")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("Invalid DATABASE_URL") from None
        if url.drivername not in {"sqlite+aiosqlite", "postgresql+asyncpg"}:
            raise ValueError("Use sqlite+aiosqlite or postgresql+asyncpg")
        if not url.database:
            raise ValueError("DATABASE_URL must include a database")
        return value


class Settings(DatabaseSettings):
    bot_token: SecretStr
    bot_username: str
    instagram_handle: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    owner_id: int = Field(gt=0)

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: SecretStr) -> SecretStr:
        try:
            validate_token(value.get_secret_value())
        except TokenValidationError:
            raise ValueError("Invalid BOT_TOKEN") from None
        return value

    @field_validator("bot_username", "instagram_handle", mode="before")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip().removeprefix("@")

    @field_validator("bot_username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", value):
            raise ValueError("Invalid BOT_USERNAME")
        if not value.lower().endswith("bot"):
            raise ValueError("BOT_USERNAME must end with bot")
        return value

    @field_validator("instagram_handle")
    @classmethod
    def validate_instagram_handle(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", value):
            raise ValueError("Invalid INSTAGRAM_HANDLE")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()


DEFAULT_TIMEZONE = ZoneInfo("Asia/Tashkent")
