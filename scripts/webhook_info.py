"""Read getWebhookInfo without placing tokens in shell arguments or output."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aiogram import Bot  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from bot import texts  # noqa: E402
from bot.config import Settings  # noqa: E402


async def check(settings, *, factory=Bot, emit=print):
    try:
        async with asyncio.timeout(15), factory(settings.bot_token.get_secret_value()) as bot:
            info = await bot.get_webhook_info()
    except Exception:
        emit(texts.WEBHOOK_INFO_FAILED)
        return False
    expected = settings.webhook_url if settings.use_webhook else ""
    matches = info.url == expected
    emit(texts.webhook_info_status(matches, info.pending_update_count, info.last_error_date))
    return matches


def main():
    try:
        settings = Settings()
    except ValidationError:
        print(texts.CONFIG_ERROR)
        return 1
    return 0 if asyncio.run(check(settings)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
