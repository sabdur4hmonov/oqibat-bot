"""Unauthenticated liveness projection; no database queries or credentials."""

import time

from aiohttp import web

STATE_KEY = web.AppKey("oqibat_health", object)


def snapshot(runtime, *, now=None):
    tick = getattr(getattr(runtime, "scheduler", None), "last_tick_at", None)
    age = None if tick is None else max(0, (time.monotonic() if now is None else now) - tick)
    healthy = age is not None and age <= 120
    return {
        "status": "ok" if healthy else "unhealthy",
        "last_tick_age_seconds": round(age, 3) if age is not None else None,
        "send_queue_length": getattr(getattr(runtime, "sender", None), "queue_length", 0),
    }, 200 if healthy else 503


async def healthz(request):
    data, status = snapshot(request.app[STATE_KEY])
    return web.json_response(data, status=status, headers={"Cache-Control": "no-store"})


def install_health(app, runtime):
    app[STATE_KEY] = runtime
    app.router.add_get("/healthz", healthz)
