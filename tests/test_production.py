import asyncio
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import ErrorEvent
from aiohttp import web
from test_challenge_flows import command_update
from test_webapp import http

from bot.handlers.errors import handle_error
from bot.handlers.health import install_health, snapshot
from bot.services.error_alerts import ErrorAlerts
from bot.services.scheduler import Scheduler
from bot.services.sender import Sender
from bot.services.webapp import polling_webapp
from scripts import healthcheck, webhook_info

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    value = 0

    def now(self):
        return self.value


class LocalSend:
    async def send(self, chat_id, operation, **kwargs):
        assert kwargs["report_failures"] is False
        return await operation()


def alerts(clock):
    bot = SimpleNamespace(send_message=AsyncMock(return_value=object()))
    return ErrorAlerts(
        bot,
        LocalSend(),
        123,
        clock=clock.now,
        utc_clock=lambda: datetime(2026, 11, 12, 10, tzinfo=UTC),
    )


async def test_alert_sanitization_aggregation_boundary_and_delivery_delay():
    clock = Clock()
    notice = alerts(clock)
    notice.record(ValueError("TOKEN secret user-message <b>"), "handler", -1)
    assert await notice.flush()
    body = notice.bot.send_message.call_args.args[1]
    assert all(word not in body for word in ["TOKEN", "secret", "user-message", '<b>"'])
    assert "ValueError" in body and "2026-11-12 10:00:00 UTC" in body and "Chat: -1" in body
    for _ in range(7):
        notice.record(RuntimeError("private"), "scheduler.daily", -2)
    clock.value = 599.99
    assert not await notice.flush()
    clock.value = 600
    assert await notice.flush()
    body = notice.bot.send_message.call_args.args[1]
    assert "Hodisalar: 7" in body and "qo‘shimcha xatolar: 6" in body
    assert notice.bot.send_message.await_count == 2
    # An alert queued late must reserve its cooldown at the actual attempt.
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(chat, operation, **kwargs):
        entered.set()
        await release.wait()
        return await operation()

    clock.value = 1200
    notice.record(KeyError("hidden"), "sender", -3)
    with patch.object(notice.sender, "send", side_effect=delayed):
        task = asyncio.create_task(notice.flush())
        await entered.wait()
        clock.value = 1800
        assert not await notice.flush()
        release.set()
        await task
    notice.record(ValueError(), "handler")
    clock.value = 2399
    assert not await notice.flush()
    clock.value = 2400
    assert await notice.flush()


async def test_failed_alert_retained_rate_limited_and_cannot_recurse():
    clock = Clock()
    notice = alerts(clock)
    notice.bot.send_message.side_effect = RuntimeError("do not expose token")
    notice.record(ValueError("message"), "unknown user text", "not an id")
    assert not await notice.flush() and notice.pending == 1
    assert not await notice.flush() and notice.bot.send_message.await_count == 1
    notice.bot.send_message.side_effect = None
    clock.value = 600
    assert await notice.flush()
    body = notice.bot.send_message.call_args.args[1]
    assert "unknown user text" not in body and "Joy: other" in body and "Chat: —" in body
    disabled = ErrorAlerts(None, None, None)
    disabled.record(RuntimeError(), "handler")
    assert not await disabled.flush() and disabled.pending == 0


async def test_slow_telegram_confirmation_cannot_shorten_alert_interval():
    clock = Clock()
    notice = alerts(clock)

    async def slow(*args):
        clock.value += 30
        return object()

    notice.bot.send_message.side_effect = slow
    notice.record(ValueError(), "handler")
    assert await notice.flush()
    notice.record(ValueError(), "handler")
    clock.value = 600
    assert not await notice.flush()
    clock.value = 630
    assert await notice.flush()


async def test_periodic_worker_first_alert_and_shutdown():
    notice = alerts(Clock())
    task = asyncio.create_task(notice.run())
    try:
        notice.record(ValueError(), "handler")
        for _ in range(30):
            if notice.bot.send_message.await_count:
                break
            await asyncio.sleep(0)
        assert notice.bot.send_message.await_count == 1
        notice.record(ValueError(), "handler")
        await asyncio.sleep(0)
        assert notice.bot.send_message.await_count == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_handler_and_scheduler_hooks_do_not_break_work(sessions):
    notify = SimpleNamespace(record=AsyncMock())
    # Production recording is synchronous; use a plain collector for adapters.
    events = []
    notify.record = lambda *a, **kw: events.append((a, kw))
    event = ErrorEvent(update=command_update("private text"), exception=ValueError("TOKEN"))
    assert await handle_error(event, notify)
    assert events[0][0][1:] == ("handler", -1)
    scheduler = Scheduler(sessions, hooks={"daily": AsyncMock(side_effect=RuntimeError("secret"))})
    scheduler.on_error = notify.record
    assert await scheduler._process("daily", SimpleNamespace(id=-4), None) is False
    assert events[-1][0][1:] == ("scheduler.daily", -4)
    scheduler.hooks.clear()
    await scheduler.tick()
    previous = scheduler.last_tick_at
    assert previous is not None
    scheduler.maintenance = [AsyncMock(side_effect=RuntimeError("private"))]
    with pytest.raises(RuntimeError):
        await scheduler.tick()
    assert scheduler.last_tick_at == previous and events[-1][0][1] == "scheduler.tick"
    scheduler.on_error = lambda *a, **kw: 1 / 0
    assert await scheduler._process("daily", SimpleNamespace(id=-5), None) is False


async def test_repeated_sender_failures_counted_and_alert_delivery_exempt(sessions, fake_clock):
    sender = Sender(sessions, clock=fake_clock)
    events = []
    sender.on_failure = lambda *a, **kw: events.append((a, kw))

    async def fail():
        raise RuntimeError("TOKEN never include")

    try:
        for _ in range(2):
            assert await sender.send(-1, fail) is None
        assert events == []
        await sender.send(-1, fail)
        assert events[0][1]["count"] == 3
        for _ in range(4):
            await sender.send(123, fail, report_failures=False)
        assert len(events) == 1
        await sender.send(-1, fail)
        assert events[-1][1]["count"] == 1
        fake_clock.value += 601
        await sender.send(-1, fail)
        assert len(events) == 2
    finally:
        await sender.close()


@pytest.mark.parametrize(
    "tick,now,status", [(None, 0, 503), (0, 120, 200), (0, 120.01, 503), (10, 5, 200)]
)
def test_health_boundary(tick, now, status):
    runtime = SimpleNamespace(
        scheduler=SimpleNamespace(last_tick_at=tick), sender=SimpleNamespace(queue_length=9)
    )
    data, actual = snapshot(runtime, now=now)
    assert actual == status and data["send_queue_length"] == 9
    assert set(data) == {"status", "last_tick_age_seconds", "send_queue_length"}


async def test_health_http_503_to_200_to_stale_no_auth_or_database():
    runtime = SimpleNamespace(
        scheduler=SimpleNamespace(last_tick_at=None), sender=SimpleNamespace(queue_length=3)
    )
    app = web.Application()
    install_health(app, runtime)
    async with http(app) as client:
        assert (await client.get("/healthz")).status == 503
        runtime.scheduler.last_tick_at = time.monotonic()
        response = await client.get("/healthz")
        assert response.status == 200 and (await response.json())["send_queue_length"] == 3
        assert response.headers["Cache-Control"] == "no-store"
        runtime.scheduler.last_tick_at -= 121
        assert (await client.get("/healthz")).status == 503


async def test_production_polling_health_only_server_lifecycle(settings):
    runtime = SimpleNamespace(
        scheduler=SimpleNamespace(last_tick_at=time.monotonic()),
        sender=SimpleNamespace(queue_length=0),
    )
    production = settings.model_copy(update={"environment": "production", "webhook_port": 0})
    original = web.TCPSite
    sites = []

    def site(*a, **kw):
        value = original(*a, **kw)
        sites.append(value)
        return value

    with patch("bot.services.webapp.web.TCPSite", side_effect=site):
        async with polling_webapp(runtime, None, production):
            assert sites[0]._server.is_serving()
            app = sites[0]._runner.app
            assert {route.resource.canonical for route in app.router.routes()} == {"/healthz"}
        assert not sites[0]._server.is_serving()


def test_stdlib_health_probe_success_and_failure(monkeypatch):
    monkeypatch.setenv("WEBHOOK_PORT", "8080")
    response = SimpleNamespace(status=200)
    with patch.object(healthcheck, "urlopen") as open_url:
        open_url.return_value.__enter__.return_value = response
        assert healthcheck.main() == 0
        open_url.side_effect = OSError("closed")
        assert healthcheck.main() == 1
    monkeypatch.setenv("WEBHOOK_PORT", "not a port")
    assert healthcheck.main() == 1


def test_installed_direct_pins_and_dev_split():
    runtime = (ROOT / "requirements.txt").read_text().splitlines()
    assert len(runtime) == 9
    for line in runtime:
        package, pinned = line.split("==")
        assert version(package.split("[")[0]) == pinned
        assert not package.startswith(("pytest", "ruff"))
    dev = (ROOT / "requirements-dev.txt").read_text().splitlines()
    assert dev[0] == "-r requirements.txt"
    assert {line.split("==")[0] for line in dev[1:]} == {"pytest", "pytest-asyncio", "ruff"}
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "requirements-dev" not in dockerfile and "HEALTHCHECK" in dockerfile


async def test_webhook_info_checks_expected_url_without_logging_raw_errors(settings):
    bot = AsyncMock()
    bot.__aenter__.return_value = bot
    info = SimpleNamespace(
        url="",
        pending_update_count=2,
        last_error_date=None,
        last_error_message="TOKEN user-message",
        ip_address="private",
    )
    bot.get_webhook_info.return_value = info
    output = []
    assert await webhook_info.check(settings, factory=lambda token: bot, emit=output.append)
    assert "mos" in output[-1] and "2" in output[-1]
    info.url = "https://different.invalid/secret-path"
    assert not await webhook_info.check(settings, factory=lambda token: bot, emit=output.append)
    bot.get_webhook_info.side_effect = RuntimeError("TOKEN user-message")
    assert not await webhook_info.check(settings, factory=lambda token: bot, emit=output.append)
    assert all(
        term not in "\n".join(output)
        for term in ["TOKEN", "user-message", "secret-path", "private"]
    )
