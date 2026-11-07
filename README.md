# Oqibat Bot

**Guruhda oqibat bo‘lsin.** Telegram group engagement bot for Uzbekistan.
Python 3.12, aiogram 3, SQLAlchemy 2 async, Alembic. Phase 0 implements the foundation
and private `/start` and `/help`. Phase 0.5 adds shared scale services; product behavior for
challenges and games remains in later phases. Phase 1 implements group onboarding,
member consent and admin settings; Phase 2 adds daily posts, content rotation, quiet hours
and daily check-in points. Phase 3 adds challenges, point ledgers, penalties and leaderboards.

## Windows PowerShell setup

Install Python 3.12 from python.org with the Python launcher, then open PowerShell:

```powershell
Set-Location 'D:\Coding projects\oqibat bot'
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

If activation is blocked, no policy change is needed: use
`.\.venv\Scripts\python.exe` instead of `python`, and
`.\.venv\Scripts\alembic.exe`, `pytest.exe`, `ruff.exe` for the commands below.
On this development machine Python 3.12 was installed with `uv python install 3.12`
and the environment created with `uv venv --python 3.12 .venv`.

Create a bot with Telegram **@BotFather** (`/newbot`). Set these local `.env` values:

| Variable | Value |
| --- | --- |
| `BOT_TOKEN` | Token from BotFather; keep it private |
| `BOT_USERNAME` | Your bot username, e.g. `OqibatBot` (optional leading `@`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./oqibat.db` for development |
| `INSTAGRAM_HANDLE` | Your Instagram username, without a URL |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `OWNER_ID` | Your positive numeric Telegram user ID |
| `ENVIRONMENT` | `development` (default) or `production`; production requires PostgreSQL |
| `DB_POOL_SIZE` | 10–20 PostgreSQL connections (default 15, overflow disabled) |
| `USE_WEBHOOK` | `false` (default) for polling; `true` for the aiohttp webhook server |
| `WEBHOOK_URL` | Full public HTTPS URL including path, e.g. `https://bot.example.com/telegram` |
| `WEBHOOK_SECRET` | Random private header secret: 1–256 letters/digits/`_`/`-` |
| `WEBHOOK_HOST` | Local bind address, default `127.0.0.1` |
| `WEBHOOK_PORT` | Local HTTP port behind a TLS reverse proxy, default `8080` |

The example token is a placeholder. Do not commit `.env` or send the token in chat.
The username is checked against Telegram's `getMe` before polling. Secrets are
hidden in configuration representations/errors and redacted in runtime logs.

Create the database and start the bot, from the repository root:

```powershell
alembic upgrade head
python -m bot --check
python -m bot
```

`--check` validates configuration and all modeled tables/columns; it does
not contact Telegram or authenticate the token. `python -m bot` registers commands
and runs long polling until Ctrl+C. Migrations read only `DATABASE_URL`, so they
work before Telegram credentials are set. Startup never creates tables implicitly.
Run `alembic upgrade head` after pulling schema changes. Never change a committed
migration; create a new revision for every later schema change.

The database URL can also be `postgresql+asyncpg://user:password@localhost/oqibat`.
Production requires this PostgreSQL URL and a pool size from 10 to 20 (default 15),
with overflow disabled. SQLite remains for development and isolated tests; it is not
the production choice for 10,000 groups. Live PostgreSQL verification still requires
a PostgreSQL server. All stored timestamps are timezone-aware UTC at the ORM
boundary. SQLite values are reattached to UTC when loaded; naive input is rejected.
Chat-local clock settings default to Asia/Tashkent (daily 09:00, quiet 23:00–08:00).
The bulk scheduler runs every 30 seconds and currently posts daily messages and assigns challenges.
An independent one-second loop resolves deadlines; queued sends never hold expiry state open.
Games arrive in later phases. Daily timing includes the stable 0–15 minute
offset, so a time set two minutes ahead can post two to seventeen minutes later, plus
up to one scheduler interval. Quiet hours defer daily delivery until quiet end.

## Telegram checks

Group upgrades to supergroups are handled automatically: one transaction moves all
chat-owned records, preserves settings and history, and leaves a durable inactive alias
for the old ID. Runtime caches and queued API destinations follow the new ID. Repeated
migration updates are safe. When both IDs already have data, opt-out wins, duplicate
delivery/point references are merged, and conflicting point amounts abort the transaction
for operator review. Original message IDs retain their original chat scope. Anonymous
administrators are recognized only when the message's sender chat is that same group.

1. Botning shaxsiy chatini oching va **Start** tugmasini bosing.
2. Salomlashuv, “Guruhda oqibat bo‘lsin”, Instagram manzili va guruhga qo‘shish
   tugmasi borligini tekshiring.
3. `/help` yuboring. Yordam va shu tugma chiqishi kerak.
4. “Botni guruhingizga qo‘shing” tugmasini bosing. Telegram guruh tanlash va
   administrator huquqlarini berish oynasini ochishi kerak.
5. Botni administrator qiling. Guruhdagi “O‘yinga qo‘shilish” tugmasini bosing.
   `/chiqish` bilan chiqishingiz, `/qoshilish` bilan qayta qo‘shilishingiz mumkin.
   Admin bo‘lsangiz, `/sozlamalar` menyusini tekshiring. O‘yinlar keyingi bosqichlarda qo‘shiladi.
6. Botni to‘xtatish uchun PowerShell oynasida **Ctrl+C** bosing.

Only implemented commands are registered. The group scope currently includes `/help`,
`/qoshilish`, `/chiqish`, `/sozlamalar`, `/vazifa`, `/men` and `/top`. Polling requests
`message`, `callback_query`, `my_chat_member`, `chat_member` and `poll_answer` updates;
group updates track onboarding and membership. Incoming activity and private reachability
are buffered without opting anyone into a group. The activity middleware also refreshes
the admin cache on membership updates.

## Scale services and rules for later phases

Group setup is automatic when Telegram sends `my_chat_member`: the bot explains missing
admin rights, welcomes the group when promoted, and marks the chat inactive when removed.
Only opted-in, active members will be eligible for later random tasks. Leaving the group
clears consent; rejoining requires opting in again. `/chiqish` also cancels that member's
pending challenges without applying a penalty.

Admins use `/sozlamalar` to edit timezone, daily toggle/time, challenge count/duration,
penalty mode, mute duration, missed-task threshold, and quiet hours. Buttons edit one menu
message. Timezone, time and threshold inputs use a reply prompt tied to that admin/chat
for five minutes; changing admins invalidates the permission cache. Numeric thresholds
are limited to 1–100 as a small input bound. Chat activity, bot-admin status, title, IDs
and timestamps are system metadata and are updated from Telegram rather than edited here.

Run exactly **one bot process** for this deployment. Its shared outbound queue, caches
and chat locks are process-local. Multiple workers would require shared coordination.
This foundation targets 10,000+ groups; the local simulation measures scheduling/DB
overhead and does not prove end-to-end Telegram or production server capacity.

- Use the runtime's **single** `sender` instance. `await sender.send(chat_id, operation,
  priority=Priority.GAME/CHALLENGE/BULK)` queues sends/edits; do not construct a sender
  per handler. It limits all attempts (including retries) to 25/second globally and
  18/minute per chat in rolling windows, with at most 25 requests in flight. The waiting
  queue caps at 20,000 items; a closed/full queue returns `None`. A failed send is not
  a successful job. One paused chat does not block other ready chats. Priority can
  reorder queued messages; it cannot recall an already dispatched request.
- Retry once after `retry_after`. Telegram provides no global/chat scope indicator,
  so an ambiguous 429 pauses the entire queue. Set `retry_scope="chat"` only for a
  known chat-specific limit. Use `sender.answer_callback_query(bot, query_id, ...)`
  for immediate callback acknowledgements/popups; it bypasses the message queue.
  Forbidden sends clear private reachability or group activity; other failures log and
  return `None`. Clean shutdown cancels pending sends and propagates cancellation.
- `ActivityBuffer.observe` coalesces names and last-seen timestamps entirely in memory.
  Flush runs every 60 seconds and on clean shutdown, in one transaction with one upsert
  per affected table per 100-row chunk. Two tables require two statements, rather than
  a write per message. It updates only known active groups and preserves opt-in flags.
  Failed flushes retain rows, with newer observations winning. Last-seen activity is
  eventually consistent; a crash can lose the last minute of observations.
- `pending.contains(chat_id, user_id)` and the injected `has_pending_challenge` use a
  startup-loaded set, with no per-message SQL. Use `runtime.challenges.create/resolve`
  for challenge status changes so the set changes only after a successful commit.
- `admins.get(chat_id)` caches admin IDs for 600 seconds and coalesces simultaneous
  requests. Membership updates invalidate/refresh it. Fetch failures propagate so
  permission checks and penalties fail closed.
- All game/session creation and mutation must use `game_sessions.create/change`.
  That repository holds a shared per-chat lock across the database transaction.
  Its transformation callback is synchronous; do not send messages or perform I/O
  while holding the state lock. Game scheduler hooks must use the same repository.
- Onboarding/settings must call `initialize_schedule(chat, now)` when saving that
  one chat. NULL timestamps mean disabled/uninitialized work. No startup/tick scan
  initializes every chat. The new migration preserves existing rows with NULL due
  timestamps; future onboarding/settings initialize them as groups are configured.
- `Scheduler` selects only indexed due rows, ordered by due time, at most 500 per kind.
  Job kinds progress concurrently, with up to 25 callbacks per kind; bulk callbacks
  cannot occupy all game callback slots. The sender still enforces one global limit.
  The `daily`, `challenge` and `expire` hooks are registered. Register `weekly` and `game` in their product
  phases. A chat hook returns `True` only after success; its next UTC timestamp is then
  recomputed with a conditional bulk update. Missing hooks keep due work intact;
  failed hooks log the failure and back off that chat/job for ten minutes.
  Expiry/game hooks run in a separate one-second loop with their own lock, independent
  of bulk work. They must persist their own status/deadline transition before returning
  success. Keep the scheduled-post idempotency ledger for daily/weekly sends.
  A chat hook can return an aware UTC datetime to defer its due time, for example until
  quiet end, instead of losing the job or repeatedly querying it during quiet hours.
- Daily offsets are stable BLAKE2 hash values, 0–900 seconds after the configured local
  daily time. Sunday summaries use 0–3599 seconds after local 20:00. Local recurrence
  is recomputed before converting to UTC, including across daylight-saving changes.
- Every five minutes an INFO log reports `queue_length`, `updates_per_minute` (rolling
  last minute) and `last_tick_duration_ms`. Monitor these before expanding workload.
  Queued sends and caches are memory-only; they are not a durable message broker.

## Daily delivery and check-ins

Daily delivery reserves a unique `(chat_id, kind, local_date)` row before sending and
records `sent`/`failed`, Telegram message ID, post time and content key afterward.
Restarting never automatically replays a reserved/failed row: Telegram has no send
idempotency key, so a lost response cannot establish whether delivery happened. This
chooses duplicate prevention over retrying an ambiguous delivery. Review reserved/failed
rows and logs manually; a crash between reservation and send can leave that day's post
undelivered. Content is not repeated in a group until all current items have been used;
then the oldest-used item is eligible again. Empty banks skip cleanly. Restart to reload
edited UTF-8 JSON banks.

An opted-in active member's first message after the daily post earns +1 for that local
date. Normal messages check cached post/consent data only; rewards are coalesced and
flushed to the point ledger every 60 seconds and on clean shutdown. A unique event
reference prevents a duplicate award after restart. A crash can lose an unflushed
check-in; the member's next message that day can qualify again. Future stats commands
flush queued check-ins before reading totals. Replying in the same second as the post
counts when the message ID is later.

## Challenges and points

Admins can use `/vazifa` for a random task, or select its format with `/vazifa video`
(round video), `/vazifa ovoz`, `/vazifa surat`, `/vazifa matn`. Content must include that
format. Forced tasks still respect quiet hours and the one-pending-task-per-chat rule.
Automatic tasks follow the configured daily count/non-quiet slots. The weighted picker
uses opted-in active members only, favors longer waits and excludes picks within the
last 24 hours when rested members are available.

Only the assigned user can complete a task, with the correct message kind after the
task message and before its deadline; no reply is required. Video notes earn +15,
voice/photo +10 and text +5. Completion resets consecutive misses. Status, streak and
ledger entries commit atomically; duplicate media updates cannot award twice.
Wrong kinds/unassigned users use the pending cache and perform no challenge SQL.

Missed tasks deduct 5 in points/mute/kick modes; `off` applies no penalty. Points mode
mentions up to five unannounced missed-task debtors in the next daily post. Mute/kick
require a supergroup and the bot's restrict-members right. All administrators, the
group creator and configured bot owner are protected; the target is checked again
immediately before moderation, including after queue delays. Permission failures
skip moderation. Kick starts only at the configured miss threshold, bans then unbans
with `only_if_banned=True`; the ban also expires automatically after five minutes as
a failsafe if unban delivery fails. No moderation runs without configured owner ID.

`/men` shows the user's ledger sum and completed/missed task counts. `/top` shows
the local Monday-based week and all-time top ten. Both flush queued check-ins first.
Balances are always SUM over the immutable event ledger; they are never mutable counters.

## Optional production webhook

Keep `USE_WEBHOOK=false` for local polling. For a production server, set
`ENVIRONMENT=production`, the PostgreSQL URL, `USE_WEBHOOK=true`, your full HTTPS URL,
a fresh `WEBHOOK_SECRET`, and the bind host/port. Generate a secret locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
alembic upgrade head
python -m bot --check
python -m bot
```

Terminate TLS at your reverse proxy and forward the URL path to
`http://127.0.0.1:8080`, preserving `X-Telegram-Bot-Api-Secret-Token` and the request
body. Bind to `0.0.0.0` only if your container/network setup requires it. The app checks
the secret header before dispatching updates and waits for update processing before
acknowledging it. Telegram registration uses the same five allowed update types.
Webhook registration happens after the listener starts. Ctrl+C cleans up the server,
background tasks and database pool; it leaves the webhook registered so Telegram can
retry while the server is down. Switching back to polling removes the webhook with
`drop_pending_updates=False`. Do not run both transports simultaneously.

## Isolated scheduler load simulation

```powershell
python scripts/simulate_load.py
python scripts/simulate_load.py --ticks 10
```

This creates and migrates a temporary SQLite database with 5,000 fake chats. Every chat
has daily, challenge and weekly work due. A tick processes at most 500 of each (1,500
items); ten ticks drain all 15,000 due items. The script prints duration and counts for
each tick, then removes the test database. It ignores your application database URL
and makes no Telegram requests. Hooks are simulated successes; delivery time and real
content/game work are outside this measurement.

## Development checks

```powershell
pytest
ruff check .
alembic check
```

Tests use temporary SQLite databases and mocked Telegram sessions; no real bot token
or network is needed. They cover config validation, escaping, normalization, migrations,
schema constraints, UTC conversion, sender failures, routing and startup. Manual live
Telegram checks require your local `.env` credentials.

See [data/README.md](data/README.md) for the six content bank schemas and three
sample objects per bank. The planned modules for later phases are documentation-only
placeholders. Implementation rules and progress are in `AGENTS.md`, `docs/PLAN.md`
and `docs/PROGRESS.md`.

Official references used for the foundation:
[aiogram polling](https://docs.aiogram.dev/en/latest/dispatcher/dispatcher.html),
[aiogram errors](https://docs.aiogram.dev/en/latest/dispatcher/errors.html),
[Telegram commands](https://core.telegram.org/bots/api#setmycommands),
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
[aiogram webhook](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html),
[Telegram webhook API](https://core.telegram.org/bots/api#setwebhook).
