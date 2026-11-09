"""Optional same-process aiohttp hosting, shared with webhook or alongside polling."""

import asyncio
import json
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from aiohttp import web

from bot import texts
from bot.handlers import webapp as handlers

DIRECTORY = Path(__file__).resolve().parents[1] / "webapp"


def install_webapp(app, runtime, bot, settings):
    app[handlers.STATE_KEY] = {
        "runtime": runtime,
        "bot": bot,
        "settings": settings,
        "slots": asyncio.Semaphore(5),
    }
    app.middlewares.append(handlers.middleware)
    html = (
        (DIRECTORY / "index.html")
        .read_text(encoding="utf-8")
        .replace("__TITLE__", escape(texts.WEB_COPY["title"]))
        .replace("__LOADING__", escape(texts.WEB_COPY["loading"]))
    )
    labels = "window.OQIBAT_COPY = " + json.dumps(texts.WEB_COPY, ensure_ascii=True) + ";"

    async def index(request):
        return web.Response(text=html, content_type="text/html")

    async def copy(request):
        return web.Response(text=labels, content_type="application/javascript")

    async def javascript(request):
        return web.FileResponse(DIRECTORY / "app.js")

    async def stylesheet(request):
        return web.FileResponse(DIRECTORY / "style.css")

    app.router.add_get("/webapp", index)
    app.router.add_get("/webapp/", index)
    app.router.add_get("/webapp/labels.js", copy)
    app.router.add_get("/webapp/app.js", javascript)
    app.router.add_get("/webapp/style.css", stylesheet)
    app.router.add_get("/webapp/api/profile", handlers.profile)
    app.router.add_get("/webapp/api/leaderboard", handlers.leaderboard)
    app.router.add_get("/webapp/api/achievements", handlers.achievements)


def create_webapp_app(runtime, bot, settings):
    app = web.Application(client_max_size=16384)
    install_webapp(app, runtime, bot, settings)
    return app


@asynccontextmanager
async def polling_webapp(runtime, bot, settings):
    if not settings.webapp_url:
        yield
        return
    runner = web.AppRunner(
        create_webapp_app(runtime, bot, settings), access_log=None, shutdown_timeout=10
    )
    try:
        await runner.setup()
        await web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port).start()
        yield
    finally:
        await runner.cleanup()
