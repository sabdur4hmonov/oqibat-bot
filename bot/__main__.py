"""Run with python -m bot; --check verifies config/schema without contacting Telegram."""

import argparse
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from pydantic import ValidationError
from sqlalchemy import inspect

from bot import texts
from bot.config import Settings
from bot.db.models import Base
from bot.db.session import create_engine, create_session_factory
from bot.handlers.errors import handle_error
from bot.handlers.private import create_router
from bot.services.sender import Sender
from bot.utils.logging import configure_logging

logger = logging.getLogger(__name__)
ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member", "poll_answer"]


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router())
    dispatcher.errors.register(handle_error)
    return dispatcher


async def register_commands(bot: Bot, sender: Sender) -> None:
    private = [
        BotCommand(command="start", description=texts.START_DESCRIPTION),
        BotCommand(command="help", description=texts.HELP_DESCRIPTION),
    ]
    for commands, scope in (
        (private, BotCommandScopeAllPrivateChats()),
        ([], BotCommandScopeAllGroupChats()),
    ):
        result = await sender.send(
            None, lambda commands=commands, scope=scope: bot.set_my_commands(commands, scope=scope)
        )
        if result is not True:
            raise RuntimeError("Command registration failed")


async def run(settings: Settings, *, check_only: bool = False) -> None:
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
            if not set(Base.metadata.tables).issubset(tables):
                raise RuntimeError("Database schema missing; run alembic upgrade head")
        if check_only:
            print(texts.CHECK_OK)
            return
        sessions = create_session_factory(engine)
        sender = Sender(sessions)
        async with Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as bot:
            identity = await bot.get_me()
            if (identity.username or "").lower() != settings.bot_username.lower():
                raise RuntimeError("BOT_USERNAME does not match the token's bot")
            await register_commands(bot, sender)
            logger.info("Starting long polling")
            await create_dispatcher().start_polling(
                bot,
                allowed_updates=ALLOWED_UPDATES,
                settings=settings,
                sessions=sessions,
                sender=sender,
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Oqibat Bot")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        print(texts.CONFIG_ERROR)
        raise SystemExit(1) from None
    configure_logging(
        settings.log_level,
        [
            settings.bot_token.get_secret_value(),
            settings.database_url.get_secret_value(),
        ],
    )
    try:
        asyncio.run(run(settings, check_only=args.check))
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Startup failed")
        print(texts.STARTUP_ERROR)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
