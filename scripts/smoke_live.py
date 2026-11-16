"""Read-only live smoke checks. Run explicitly with your own configured test bot."""

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from aiogram import Bot
from aiohttp import ClientSession, ClientTimeout
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot import texts  # noqa: E402
from bot.config import Settings  # noqa: E402


def health_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("HTTPS required")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials forbidden")
    return urlunsplit((parsed.scheme, parsed.netloc, "/healthz", "", ""))


async def check(settings, bot, http, output=print):
    checks = []

    def result(key, ok):
        checks.append(ok)
        output(texts.smoke_result(key, ok))

    try:
        async with asyncio.timeout(5):
            identity = await bot.get_me()
        good = (
            identity.is_bot
            and (identity.username or "").casefold() == settings.bot_username.casefold()
        )
    except Exception:
        good = False
    result("get_me", good)
    try:
        async with asyncio.timeout(5):
            info = await bot.get_webhook_info()
        good = (info.url or "") == (settings.webhook_url or "" if settings.use_webhook else "")
        good = good and not (
            getattr(info, "last_error_date", None) and getattr(info, "pending_update_count", 0)
        )
    except Exception:
        good = False
    result("webhook", bool(good))
    url = settings.webapp_url
    if not url:
        result("webapp", False)
        result("health", False)
    else:
        try:
            health_url(url)
            async with http.get(url, allow_redirects=False) as response:
                good = response.status == 200
        except Exception:
            good = False
        result("webapp", good)
        try:
            async with http.get(health_url(url), allow_redirects=False) as response:
                data = await response.json()
                age = data.get("last_tick_age_seconds")
                good = (
                    response.status == 200
                    and data.get("status") == "ok"
                    and isinstance(age, (int, float))
                    and 0 <= age <= 120
                    and isinstance(data.get("send_queue_length"), int)
                    and data["send_queue_length"] >= 0
                )
        except Exception:
            good = False
        result("health", good)
    output(texts.SMOKE_OK if all(checks) else texts.SMOKE_BAD)
    return all(checks)


async def run(settings):
    async with Bot(settings.bot_token.get_secret_value()) as bot:
        async with ClientSession(timeout=ClientTimeout(total=5)) as http:
            return await check(settings, bot, http)


def main():
    try:
        settings = Settings()
    except ValidationError:
        print(texts.SMOKE_CONFIG)
        return 1
    try:
        return 0 if asyncio.run(run(settings)) else 1
    except Exception:
        print(texts.SMOKE_BAD)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
