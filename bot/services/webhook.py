"""aiohttp webhook transport using aiogram's authenticated request handler."""

import asyncio
from urllib.parse import urlsplit

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web


def create_webhook_app(dispatcher, bot, settings, workflow: dict) -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret.get_secret_value(),
        handle_in_background=False,
        **workflow,
    ).register(app, path=urlsplit(settings.webhook_url).path)
    setup_application(app, dispatcher, bot=bot, **workflow)
    return app


async def serve_webhook(dispatcher, bot, settings, sender, workflow: dict) -> None:
    app = create_webhook_app(dispatcher, bot, settings, workflow)
    runner = web.AppRunner(app)
    try:
        await runner.setup()
        await web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port).start()
        result = await sender.send(
            None,
            lambda: bot.set_webhook(
                url=settings.webhook_url,
                secret_token=settings.webhook_secret.get_secret_value(),
                allowed_updates=workflow["allowed_updates"],
                drop_pending_updates=False,
            ),
        )
        if result is not True:
            raise RuntimeError("Webhook registration failed")
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
