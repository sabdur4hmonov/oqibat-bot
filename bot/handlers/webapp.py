"""HTTP adapters: authenticate every API call and verify live Telegram membership."""

import asyncio
import logging
import re

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiohttp import web

from bot import texts
from bot.db.models import Chat
from bot.services import webapp_data
from bot.services.webapp_auth import Identity, InitDataError, validate_init_data

STATE_KEY = web.AppKey("oqibat_webapp", dict)
IDENTITY_KEY = web.RequestKey("oqibat_identity", Identity)
logger = logging.getLogger(__name__)


def member_allowed(member):
    return member.status in {"creator", "administrator", "member"} or (
        member.status == "restricted" and bool(getattr(member, "is_member", False))
    )


@web.middleware
async def middleware(request, handler):
    if not request.path.startswith("/webapp"):
        return await handler(request)
    state = request.app[STATE_KEY]
    api = request.path.startswith("/webapp/api/")
    try:
        if api:
            identity = validate_init_data(
                request.headers.get("X-Telegram-Init-Data", ""),
                state["settings"].bot_token.get_secret_value(),
            )
            request[IDENTITY_KEY] = identity
            try:
                async with asyncio.timeout(1):
                    await state["slots"].acquire()
            except TimeoutError:
                raise web.HTTPServiceUnavailable() from None
            try:
                async with asyncio.timeout(10):
                    response = await handler(request)
            finally:
                state["slots"].release()
        else:
            response = await handler(request)
    except InitDataError as error:
        response = web.json_response(
            {"error": texts.WEB_COPY["expired" if str(error) == "expired" else "auth_error"]},
            status=401,
        )
    except web.HTTPException as error:
        label = {
            400: "bad_request",
            403: "forbidden",
            404: "not_found",
            405: "read_only",
            503: "busy",
        }.get(error.status, "error")
        response = web.json_response({"error": texts.WEB_COPY[label]}, status=error.status)
    except (TimeoutError, TelegramRetryAfter) as error:
        if isinstance(error, TelegramRetryAfter):
            sender = state["runtime"].sender
            sender.limiter.pause(None, sender.clock.now() + error.retry_after)
            sender._wake.set()
        response = web.json_response(
            {"error": texts.WEB_COPY["busy"]}, status=503, headers={"Retry-After": "10"}
        )
    except Exception:
        logger.exception("Mini App request failed")
        response = web.json_response({"error": texts.WEB_COPY["error"]}, status=500)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://telegram.org; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
        "frame-ancestors https://*.telegram.org https://telegram.org https://t.me"
    )
    return response


async def group_for(request):
    state = request.app[STATE_KEY]
    raw = request.query.get("chat_id", "")
    if not re.fullmatch(r"-[0-9]{1,19}", raw) or not -(2**63) <= int(raw) < 0:
        raise web.HTTPBadRequest()
    runtime = state["runtime"]
    target = runtime.locks.resolve(int(raw))
    async with runtime.sessions() as session:
        chat = await session.get(Chat, target)
    if not chat or not chat.is_active or not chat.bot_is_admin:
        raise web.HTTPForbidden()
    if runtime.sender.limiter.global_pause > runtime.sender.clock.now():
        raise web.HTTPServiceUnavailable()
    try:
        async with asyncio.timeout(5):
            member = await state["bot"].get_chat_member(target, request[IDENTITY_KEY].user_id)
    except (TelegramForbiddenError, TelegramBadRequest):
        raise web.HTTPForbidden() from None
    if not member_allowed(member):
        raise web.HTTPForbidden()
    return chat


async def profile(request):
    runtime = request.app[STATE_KEY]["runtime"]
    data = await webapp_data.profile(runtime.sessions, request[IDENTITY_KEY])
    data["avatar"] = (
        await runtime.cards.avatars.encoded(data["id"])
        if data["id"] not in runtime.owner_tools.deleted
        else None
    )
    return web.json_response(data)


async def leaderboard(request):
    scope = request.query.get("scope", "season")
    if scope not in {"season", "all"}:
        raise web.HTTPBadRequest()
    chat = await group_for(request)
    runtime = request.app[STATE_KEY]["runtime"]
    data = await webapp_data.leaderboard(runtime, chat, scope)
    avatars = await asyncio.gather(
        *(runtime.cards.avatars.encoded(item["id"]) for item in data["items"])
    )
    for item, avatar in zip(data["items"], avatars, strict=True):
        item["avatar"] = avatar
    return web.json_response(data)


async def achievements(request):
    chat = await group_for(request)
    runtime = request.app[STATE_KEY]["runtime"]
    return web.json_response(
        await webapp_data.achievements(runtime.sessions, chat, request[IDENTITY_KEY].user_id)
    )
