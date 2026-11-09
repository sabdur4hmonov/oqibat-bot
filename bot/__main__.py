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
from bot.handlers.challenges import create_router as create_challenges_router
from bot.handlers.errors import handle_error
from bot.handlers.games.easy import create_router as create_games_router
from bot.handlers.games.krokodil import create_router as create_krokodil_router
from bot.handlers.games.mafia import create_router as create_mafia_router
from bot.handlers.games.truth_dare import create_router as create_truth_dare_router
from bot.handlers.group_setup import create_router as create_group_router
from bot.handlers.owner import create_router as create_owner_router
from bot.handlers.private import create_router
from bot.handlers.settings import create_router as create_settings_router
from bot.handlers.stats import create_router as create_stats_router
from bot.services.runtime import ScaleMiddleware, ScaleRuntime
from bot.services.sender import Sender
from bot.services.webhook import serve_webhook
from bot.utils.logging import configure_logging

logger = logging.getLogger(__name__)
ALLOWED_UPDATES = ["message", "callback_query", "my_chat_member", "chat_member", "poll_answer"]


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(create_owner_router())
    dispatcher.include_router(create_router())
    dispatcher.include_router(create_group_router())
    dispatcher.include_router(create_settings_router())
    dispatcher.include_router(create_challenges_router())
    dispatcher.include_router(create_stats_router())
    dispatcher.include_router(create_games_router())
    dispatcher.include_router(create_krokodil_router())
    dispatcher.include_router(create_truth_dare_router())
    dispatcher.include_router(create_mafia_router())
    dispatcher.errors.register(handle_error)
    return dispatcher


async def register_commands(bot: Bot, sender: Sender) -> None:
    private = [
        BotCommand(command="start", description=texts.START_DESCRIPTION),
        BotCommand(command="help", description=texts.HELP_DESCRIPTION),
        BotCommand(command="stats", description=texts.OWNER_STATS_DESCRIPTION),
        BotCommand(command="maxfiylik", description=texts.PRIVACY_DESCRIPTION),
        BotCommand(command="malumotlarimni_ochir", description=texts.ERASE_DESCRIPTION),
    ]
    for commands, scope in (
        (private, BotCommandScopeAllPrivateChats()),
        (
            [
                BotCommand(command=command, description=description)
                for command, description in texts.GROUP_COMMANDS.items()
            ],
            BotCommandScopeAllGroupChats(),
        ),
    ):
        result = await sender.send(
            None, lambda commands=commands, scope=scope: bot.set_my_commands(commands, scope=scope)
        )
        if result is not True:
            raise RuntimeError("Command registration failed")


async def run(settings: Settings, *, check_only: bool = False) -> None:
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_size=settings.db_pool_size
    )
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
            if not set(Base.metadata.tables).issubset(tables):
                raise RuntimeError("Database schema missing; run alembic upgrade head")
            complete = await connection.run_sync(
                lambda conn: all(
                    set(table.columns.keys()).issubset(
                        {column["name"] for column in inspect(conn).get_columns(table.name)}
                    )
                    for table in Base.metadata.tables.values()
                )
            )
            if not complete:
                raise RuntimeError("Migration missing; run alembic upgrade head")
        if check_only:
            print(texts.CHECK_OK)
            return
        sessions = create_session_factory(engine)
        async with Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ) as bot:
            identity = await bot.get_me()
            if (identity.username or "").lower() != settings.bot_username.lower():
                raise RuntimeError("BOT_USERNAME does not match the token's bot")
            async with ScaleRuntime(sessions, bot, settings) as runtime:
                await register_commands(bot, runtime.sender)
                dispatcher = create_dispatcher()
                dispatcher.update.outer_middleware(ScaleMiddleware(runtime))
                workflow = {
                    "settings": settings,
                    "sessions": sessions,
                    "allowed_updates": ALLOWED_UPDATES,
                    **runtime.workflow(),
                }
                if settings.use_webhook:
                    logger.info("Starting webhook server")
                    await serve_webhook(dispatcher, bot, settings, runtime.sender, workflow)
                else:
                    result = await runtime.sender.send(
                        None, lambda: bot.delete_webhook(drop_pending_updates=False)
                    )
                    if result is not True:
                        raise RuntimeError("Could not switch to polling")
                    logger.info("Starting long polling")
                    await dispatcher.start_polling(bot, **workflow)
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
            settings.webhook_secret.get_secret_value() if settings.webhook_secret else "",
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
