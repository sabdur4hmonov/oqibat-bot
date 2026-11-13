# Oqibat Bot

`/oyinlar` — davraning asosiy menyusi: Tez o‘yinlar, So‘z o‘yinlari,
Katta o‘yinlar va Fon o‘yini. Guruhdagi tugma o‘yinni bosgan odam nomidan
boshlaydi; `/qoshilish`, bot adminligi va bo‘sh o‘yin joyi talablari saqlanadi.
Barcha eski o‘yin buyruqlarini qo‘lda yozish mumkin; guruh buyruq menyusi sakkizta
asosiy buyruqni ko‘rsatadi. Shaxsiy menyudan guruhda o‘ynash tushuntiriladi.
Bot admin bo‘lganda uchta tez sozlash qadami chiqadi: mahalliy kunlik vaqt,
kunlik vazifalar soni va jazo turi. Har tanlov bazaga saqlanadi. Bot qayta ishga
tushsa yoki tugma eskirsa `/sozlamalar` dan davom eting. Kunlik postdagi
“🎲 Bugungi o‘yin” ham ayni ruxsat tekshiruvlari bilan bir o‘yinni taklif qiladi.

**Guruhda oqibat bo‘lsin.** Telegram group engagement bot for Uzbekistan.
Python 3.12, aiogram 3, SQLAlchemy 2 async, Alembic. Phase 0 implements the foundation
and private `/start` and `/help`. Phase 0.5 adds shared scale services. Phase 1 implements group onboarding,
member consent and admin settings; Phase 2 adds daily posts, content rotation, quiet hours
and daily check-in points. Phase 3 adds challenges, point ledgers, penalties and leaderboards.
Phase 4 adds dice duels, five-question quizzes, and would-you-rather polls. Phase 5 adds Krokodil; Phase 6 adds Haqiqat yoki jasorat. Phase 7 adds Mafia; Phase 8 adds weekly summaries and full help. Phase 9 adds shareable result cards and deployment examples. Phase 10 adds recovery/owner/privacy tools; Phase 11 adds monthly seasons, streak bonuses and achievements.

## Monthly seasons, streaks and achievements

Mini App v2 uses Telegram themes, optional haptics, loading skeletons, avatars and
medal leaderboards. Profile shows a passive Daraja and next-level progress, a locked/
unlocked achievement gallery and the selected group's calendar-month countdown.
Thresholds live only in `bot/constants.py`: 0 (Yangi a’zo), 50 (Faol), 200 (Davra
yulduzi), 1000 (Oqibat ustasi). These never award/reset points. Private profile uses
all-time points across groups; `/men`, group leaderboards and card badges use that
group's all-time ledger. The card's score can still be a game/week/season result.
Buffered daily check-ins can appear after their normal 60-second flush; refreshing
the read-only app does not write points. Avatars are optional, metadata-free,
bounded in memory and removed by self-deletion. Real Telegram haptics need a phone.

`/top` uses calendar months in the group's timezone, with all-time totals alongside.
The ledger is never reset by a season change. On the first day, the previous month's
top five post from local 09:00 with a stable 0–15 minute offset; quiet hours defer it.
Cards honor `RESULT_CARDS_ENABLED` and fall back to text. Claims/recovery use the same
six-hour policy as other posts. An outage produces one report for the stored due month,
not a burst for every missed month. Existing chats are initialized in bounded migration
batches; runtime only selects indexed `next_season_at` rows that are due.

Daily check-ins award +3 on day 7 and +10 on day 30 of each unbroken sequence, in
addition to that day's +1. A missed calendar day resets the sequence; a month change
does not. Bonuses are not retroactively added to old ledger entries and are not repeated
at days 14/60 of the same sequence. Their daily reference keeps scored activity counted
once. Base points, bonus and unlock commit atomically; duplicate updates cannot repeat them.

Group `/yutuqlar` lists six milestones: first completed task, first round video, ten
Krokodil guesses, first Mafia game win, seven-day streak and thirty-day streak.
Unlocks add no extra points. The command can reconcile already-earned historical
milestones without rewriting the ledger. Short announcements are grouped at BULK
priority (up to ten unlocks per chat/message); claims prevent repeated batches.
Announcement loss is accepted on a crash; the unlock remains visible in `/yutuqlar`.
Self-deletion removes these records, and supergroup migration preserves/merges them.

## Owner tools and privacy

Phase 10 adds `/maxfiylik` (stored-data explanation), private
`/malumotlarimni_ochir` (five-minute requester-bound confirmation) and private
OWNER_ID-only `/stats`. Stats count unique consenting users, unique active users over
the last 24 hours and games started over seven days, plus queue/tick metrics.
Confirmed deletion removes the user's live rows, anonymizes linked shared game records and clears cached
references; it cancels affected pending chat effects. Delivered Telegram messages and
operator backups are not removed. Start again with `/start` to deliberately create new data.
The running process retains a temporary deletion guard to prevent stale work recreating data.

The approved crash contract keeps the Sender in memory. Recent challenge assignment/result
notifications and unconfirmed posts recover from their existing rows for six hours; old
ones are skipped. An unannounced old assignment cancels without penalty. Moderation is
never replayed by recovery. Telegram can show a repeated message after a lost confirmation;
points remain transactionally idempotent. Buffered activity and queued low-priority work
can be lost on a crash. Clean shutdown rejects new work, flushes buffers, then allows
accepted queued sends ten seconds to finish. No general durable queue/journal is used.

## Games

Participants must opt in with `/qoshilish` and the bot must be a group admin.
`/duel` opens a 90-second challenge; reply to a participant to target them. The starter
chooses 🎲/🎯/🎳; the bot rolls in the order shown on the board. Ties reroll and results
wait four seconds for the animation. `/viktorina` runs five non-anonymous 30-second quiz
polls, awards +3 per correct answer and +2 for the first correct answer, then edits the
same scoreboard. The first answer per person/question is final. With the three sample
questions, questions rotate and may repeat across the five rounds; replace the sample
bank with real owner-authored content. `/tanla` opens a non-anonymous regular poll for
60 seconds, without points. One main game can run per group, alongside duels (one per starter).
`/stop` is available to the starter or an admin; reply to a duel board to select that duel.
An anonymous admin can also stop games. Incomplete poll/dice sends are cancelled on
restart because replaying an ambiguous Telegram send could duplicate it; established
quiz questions and dice-animation deadlines resume from their saved state.

## Windows PowerShell setup

Install Python 3.12 from python.org with the Python launcher, then open PowerShell:

```powershell
Set-Location 'D:\Coding projects\oqibat bot'
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
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
| `BOT_USERNAME` | Your actual BotFather username (optional leading `@`); replace `YourBotUsername` |
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
| `RESULT_CARDS_ENABLED` | `true` (default) for winner/weekly PNG cards; `false` keeps text results |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose database settings; use a fresh random hex password |

The example token is a placeholder. Do not commit `.env` or send the token in chat.
The username is checked against Telegram's `getMe` before polling. Secrets are
hidden in configuration representations/errors and redacted in runtime logs.
`OqibatBot` belongs to someone else; do not use it. `YourBotUsername` is an intentional
placeholder, not a valid final bot username: enter your own name ending in `bot`.
Direct runtime dependencies are pinned to tested installed versions in requirements.txt.
Production installs only that file; development/tests install requirements-dev.txt,
which includes runtime plus pytest/pytest-asyncio/ruff. Docker never installs the dev file.

Create the database and start the bot, from the repository root:

```powershell
alembic upgrade head
python -m bot --check
python -m bot
```

For live testing, follow the Uzbek checklist in [docs/LIVE_TEST.md](docs/LIVE_TEST.md).
Run the preflight checker after migrations, before starting the bot:

```powershell
.\.venv\Scripts\python.exe scripts\check_env.py
```

It checks the project-root `.env` plus normal environment overrides, token syntax,
Telegram `getMe`, the username match, database connectivity and required tables/columns.
It prints Uzbek instructions and returns `0` on success or `1` on failure, without
printing credentials. The network probes have bounded timeouts. Missing SQLite files
are reported rather than created; run migrations first. This command does not poll
updates, start the scheduler, send messages or modify bot data. Tests use a fake
Telegram session, so live authentication still requires your own credentials.

`--check` validates configuration and all modeled tables/columns; it does
not contact Telegram or authenticate the token. `python -m bot` registers commands
and runs long polling until Ctrl+C. Migrations read only `DATABASE_URL`, so they
work before Telegram credentials are set. Startup never creates tables implicitly.
Run `alembic upgrade head` after pulling schema changes. Never change a committed
migration; create a new revision for every later schema change.

The database URL can also be `postgresql+asyncpg://user:password@localhost/oqibat`.
Production requires this PostgreSQL URL and a pool size from 10 to 20 (default 15),
with overflow disabled. SQLite remains for development and isolated tests; it is not
the production choice for 10,000 groups. An isolated PostgreSQL 16.14 smoke test verifies
migrations, UTC, bulk upserts, ledger uniqueness, game constraints and due scheduling.
This is not a production capacity measurement. All stored timestamps are timezone-aware UTC at the ORM
boundary. SQLite values are reattached to UTC when loaded; naive input is rejected.
Chat-local clock settings default to Asia/Tashkent (daily 09:00, quiet 23:00–08:00).
The bulk scheduler runs every 30 seconds and currently posts daily messages and assigns challenges.
An independent one-second loop resolves deadlines; queued sends never hold expiry state open.
Game and expiry deadlines use that separate loop. Daily timing includes the stable 0–15 minute
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
   Admin bo‘lsangiz, `/sozlamalar` menyusini tekshiring. To‘liq sinovlar `docs/LIVE_TEST.md` da.
6. Botni to‘xtatish uchun PowerShell oynasida **Ctrl+C** bosing.

Only implemented commands are registered. The group scope currently includes `/help`,
`/qoshilish`, `/chiqish`, `/sozlamalar`, `/vazifa`, `/men`, `/top`, `/duel`, `/viktorina`,
`/tanla`, `/krokodil`, `/hyj`, `/mafia` and `/stop`. Polling requests
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
  return `None`. Clean shutdown first drains accepted sends for up to ten seconds,
  then cancels leftovers and propagates cancellation.
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
  The `daily`, `challenge`, `weekly`, `expire` and `game` hooks are registered.
  A chat hook returns `True` only after success; its next UTC timestamp is then
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
Unconfirmed reserved/failed rows are retried by the bounded recovery pass for six hours;
older ones are marked skipped. A lost Telegram response can cause a duplicate message,
but the original business row is retained and sending never awards points again.
Content is not repeated in a group until all current items have been used;
then the oldest-used item is eligible again. Empty banks skip cleanly. Restart to reload
edited UTF-8 JSON banks.

An opted-in active member's first message after the daily post earns +1 for that local
date. Ordinary messages check cached post/consent data only. A first qualifying
check-in is a scoring action and flushes its award before the update is acknowledged;
unique event references prevent a duplicate award after restart. Buffered observations
made while the daily send itself awaits confirmation are reconciled after confirmation;
until then there is no confirmed daily-post boundary. Periodic/shutdown flush and stats
commands also flush pending check-ins. Replying in the same second as the post
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
the current calendar-month season in the chat timezone and all-time top ten. Both flush queued check-ins first.
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

Tests normally use temporary SQLite databases and mocked Telegram sessions; no real bot token
or network is needed. They cover config validation, escaping, normalization, migrations,
schema constraints, UTC conversion, sender failures, routing and startup. Manual live
Telegram checks require your local `.env` credentials.

See [data/README.md](data/README.md) for the six content bank schemas and three
sample objects per bank. Implementation rules and progress are in `AGENTS.md`, `docs/PLAN.md`
and `docs/PROGRESS.md`.

Official references used for the foundation:
[aiogram polling](https://docs.aiogram.dev/en/latest/dispatcher/dispatcher.html),
[aiogram errors](https://docs.aiogram.dev/en/latest/dispatcher/errors.html),
[Telegram commands](https://core.telegram.org/bots/api#setmycommands),
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html),
[aiogram webhook](https://docs.aiogram.dev/en/latest/dispatcher/webhook.html),
[Telegram webhook API](https://core.telegram.org/bots/api#setwebhook).


### Krokodil

`/krokodil` starts ten three-minute rounds with at least two opted-in players.
The starter hosts first; only the host's private callback popup reveals the word.
The host may replace the word twice per round, without extending the round deadline.
Guess in group chat: matching ignores apostrophe variants, punctuation and Uzbek
Cyrillic/Latin spelling differences. A correct guess earns +5, the host earns +3,
and the guesser hosts next. A timeout reveals the word and selects an opted-in host.
A host revealing the word (including inside a longer message) loses 3 points and gets
a new word in the same round. The board is edited; `/stop` remains available. Existing
rounds resume after restart. Word entries must be meaningful and at most 100 characters
to fit Telegram's private popup. Unrelated guesses use cached state without SQL.


### Haqiqat yoki jasorat

`/hyj` chooses an opted-in target at random; reply to an opted-in member to target
them instead. Only that target can choose or refuse. The choice lasts 90 seconds.
Truth gives a question and 30 minutes to answer in text or voice, for +5 points.
Truth/choice timeouts have no extra penalty. Dare assigns that same target through
the existing challenge engine, with a one-hour deadline (extended to quiet end if
needed), the usual required media type and +15/+10/+10/+5 completion points.
Dares are not assigned during quiet hours, and an existing pending challenge must
finish first; the target can still choose truth instead.

Refusing before the deadline costs only 2 points and atomically cancels a pending
dare; it never mutes or kicks. A dare left to expire without refusal follows the
normal configured challenge penalty policy. Refusal, completion and expiry cannot
all score the same task. `/stop` or target opt-out cancels without a penalty.
Established truth/dare state survives restart; an ambiguous question send cancels
with a restart notice. Outbound edits for one game are serialized independently of
state locks so a delayed question edit cannot overwrite the final result.

### Mafia (Phase 7)

`/mafia` opens a 90-second lobby for 5–15 opted-in group members. Everyone, including
the starter, joins through the private `start=mafia_<session_id>` link. A person may
reserve only one active Mafia lobby/game across all groups. At lobby close, role DMs
are prepared without active buttons. Forbidden recipients are removed, announced in
the edited group board, and roles are recalculated for the remaining players; fewer
than five cancels. Role proposals are provisional until every remaining DM succeeds.
If proposals change, earlier ones are void and the private message is edited. A generic
ambiguous delivery error cancels safely rather than silently dropping a player.

Roles follow PLAN: 1/2/3 mafia for 5–6/7–9/10–15 players, plus one doctor and commissioner.
Mafia teammates are named privately; their changing vote tally stays in their private
boards. No mafia vote means no kill. Night lasts 60 seconds, discussion 90 and the
changeable group vote 60. Night vote ties pick a random tied target; day ties eliminate
nobody. The doctor cannot self-save on consecutive nights. The commissioner checks
once per night and gets a private popup. Dead/stale/wrong-context callbacks are rejected;
every action identifies both session and round. Group and private boards are edited.

In the default base mode, town wins with no mafia; mafia wins at parity. Winning-side members earn +10 and
survivors +3 (a draw awards only survivors); opt-out/leave forfeits participation and
awards no points to that player. At 20 completed rounds or 60 minutes from lobby
creation the game is a draw; an unstarted preparation earns no points. `/stop` is
starter/admin only and notifies all players privately. Restart cancels every active
Mafia with a group apology and private notifications, preserving committed points.

`/sozlamalar` has an OFF-by-default dead-player message deletion toggle. It can be
changed during play; actual deletion checks the bot's delete right fresh. This is
best effort through the same limited GAME queue; Telegram failures do not crash play.
All Mafia sends/edits/deletes use GAME priority. Deadlines commit independently of
queued delivery. Keep one bot process: user reservations and state locks are local.

#### Extended Mafia roles (Phase 12, default OFF)

Admins can enable `extended_roles` in `/sozlamalar`; the lobby snapshots it, so changes
apply to the next game. The lobby announces the mode. The original mode stays unchanged.
Don appears at 8+ (replaces one mafia, preserving team size), Ma'shuqa at 9+ (replaces
plain town and belongs to town), Manyak at 11+ (replaces plain town and plays alone).
Don's vote resolves mafia ties and the commissioner sees him as non-mafia. Teammates
learn Don's identity privately. Ma'shuqa blocks one night action, never the same target
two nights in a row. Manyak selects one night victim and wins alive with at most one
other player. Town needs both mafia and Manyak eliminated; mafia parity wins only
after Manyak dies. Manyak's win check has precedence.

Blocks resolve first, then simultaneous mafia/Manyak attacks. The doctor protects one
target from both attackers and still saves if killed that night. A blocked self-save
does not consume the next night's self-save allowance. With Ma'shuqa in the layout,
the commissioner selects once at night and receives the result privately at dawn;
blocking yields no result. A dead commissioner gets no further private action/result.
Day votes, caps, deep-link joins, private-context checks and GAME priority remain.
Draws give only survivor points; Manyak's victory gives the usual +10 plus +3 survival.


### Weekly summary and help (Phase 8)

A shared BULK queue delivers one summary per scheduled local week on Sunday,
stably spread over 20:00–20:59:59. It shows the top five point totals since local
Monday, the most active member, completed/missed task counts and current pending
tasks, the slogan, Instagram footer and add-to-group link. "Most active" means
most distinct positive-scoring activity references, not raw message volume; Mafia
win/survival awards from the same game count as one activity. Ties use positive
points then user ID. This definition uses the existing ledger without per-message
writes or an additional activity counter.

Quiet hours defer delivery. Monday catch-up keeps the original Sunday week;
a later Sunday's summary belongs to the next week. A migrated chat keeps that week
identity even if its hash offset changes. Reservations use the existing post ledger
with the local Monday date as the weekly key. As with daily posts, unconfirmed sends
are retried only within the six-hour recovery window; a lost confirmation can cause
a repeated message, but never repeated points. Older deliveries are skipped. Large outages
produce one report for the stored due week, not a burst for every missed week.
Chat/date indexes bound point and resolved-task reporting queries. All scheduling
still uses the indexed 500-row batches, never a scan of chats.

Private and group `/help` now list every implemented command and game timing, plus
the footer and add-to-group button. Routine game/task/daily messages have no footer.

### Result cards (Phases 9, 24)

Chat cards are 1080×1080; the “📲 Story uchun” button prepares a 1080×1920
version and DMs only the human who pressed it (open /start first). Stories are not
automatically posted to the group. Original vector icons replace emoji text; the
bundled font filters unsupported glyphs. Top three use gold/silver/bronze, with
game accents and the configured Instagram handle. Small profile pictures are
cached in memory by file_id; missing/failed pictures use initials. Erasure clears
the relevant cache and prevents delayed source uploads. Already delivered Telegram
images remain outside the deletion boundary. Synthetic previews for every style,
both formats, live in [docs/design](docs/design/README.md); regenerate with
`python scripts/preview_cards.py`. Private-game positive-score results also get cards.

Weekly top-five reports are a single PNG with the full report in its caption. Completed
quiz/Krokodil scores, duel wins, completed truth/dares and Mafia winning teams get a
separate top-five result card after the normal final board. Ties/draws without a winning
result and cancelled games have no winner card. Larger Mafia teams show their first five
ranked members; every member's actual points still go into the ledger. Cards show this
game's points, not lifetime balances. `@INSTAGRAM_HANDLE` is watermarked on every card.

Rendering uses at most two worker threads, outside the event loop. The bundled Noto Sans
font supports Uzbek Latin/apostrophes and Cyrillic; its SIL OFL license and source/hash
are in [assets/fonts](assets/fonts/README.md). Long names are shortened by pixel width;
control characters are removed. Text results remain if rendering fails. Set
`RESULT_CARDS_ENABLED=false` to disable rendering/uploads. A game reserves its card once
in existing session JSON before upload; ambiguous or failed uploads are logged, not
automatically repeated after restart. Weekly photos share the existing post reservation.

## Serverga joylash: Docker Compose (tavsiya)

Quyidagi buyruqlar qo‘llanma; agent botni serverga joylamadi. Docker Desktop ishlayotgan
Windows PowerShell yoki Docker Engine + Compose o‘rnatilgan server kerak. Avval sinov
botida LIVE_TEST qadamlarini bajaring. Bitta token uchun **faqat bitta bot jarayoni**
ishlasin; bir vaqtda mahalliy polling, Compose va systemd ni ishlatmang.

1. Loyihani alohida papkaga oling. Quyidagi buyruqlarni shu papkada bajaring:

   ```powershell
   git clone https://github.com/sabdur4hmonov/oqibat-bot.git
   Set-Location oqibat-bot
   Copy-Item .env.example .env
   python -c "import secrets; print(secrets.token_hex(24))"
   notepad .env
   ```

2. BotFather tokeni, aniq `BOT_USERNAME`, `OWNER_ID`, `INSTAGRAM_HANDLE` ni kiriting.
   `POSTGRES_PASSWORD` ga hozir yaratilgan tasodifiy hex qiymatni qo‘ying.
   `POSTGRES_USER=oqibat`, `POSTGRES_DB=oqibat`, `ENVIRONMENT=production`,
   `DB_POOL_SIZE=15`, `USE_WEBHOOK=false` bo‘lsin. Compose ichidagi `DATABASE_URL`
   avtomatik `db:5432` ga sozlanadi; `.env` dagi mahalliy SQLite URL ishlatilmaydi.
   Keyinchalik bazaning parolini faqat `.env` da o‘zgartirish mavjud PostgreSQL
   foydalanuvchisi parolini o‘zgartirmaydi. `.env` ni sir saqlang.

3. Faqat shu loyiha konfiguratsiyasini tekshiring, obrazni quring va bazani tayyorlang:

   ```powershell
   docker compose -p oqibat config --quiet
   docker compose -p oqibat build bot
   docker compose -p oqibat up -d db
   docker compose -p oqibat run --rm bot alembic upgrade head
   docker compose -p oqibat run --rm bot python -m bot --check
   docker compose -p oqibat run --rm bot python scripts/check_env.py
   ```

   Oxirgi buyruq haqiqiy Telegram `getMe` bilan token/username va bazani tekshiradi,
   botni ishga tushirmaydi. Xato bo‘lsa, o‘zbekcha ko‘rsatmani bajaring. Muhit
   qiymatlari to‘liq berilsa, checker jismoniy `.env` faylisiz ham ishlaydi.
   Docker obraziga `.env` kiritilmaydi. Obraz root bo‘lmagan 10001 foydalanuvchida
   ishlaydi; Compose fayl tizimi o‘qish uchun, vaqtinchalik `/tmp` yozish uchun ochiq.

4. Tekshiruv o‘tgach, boshqa bot jarayonini to‘xtating va ishga tushiring:

   ```powershell
   docker compose -p oqibat up -d bot backups
   docker compose -p oqibat ps
   docker compose -p oqibat logs --tail 100 bot
   docker compose -p oqibat logs -f bot
   ```

   Bot boshlanishida migratsiya bajariladi; polling boshlangach shaxsiy chatda
   `/start` yuboring. Jurnalni kuzatishdan Ctrl+C bilan chiqish botni to‘xtatmaydi.
   Botni to‘xtatish: `docker compose -p oqibat stop bot`. PostgreSQL 16 alohida
   doimiy `oqibat_postgres_data` hajmida saqlanadi, porti tashqariga ochilmaydi.
   Boshqa loyihalarda ham `oqibat` nomi bo‘lsa, barcha buyruqlarda boshqa bir xil
   `-p` nomini tanlang. Global Docker tozalash buyruqlarini ishlatmang.

5. Webhook kerak bo‘lsa, oldingi “Optional production webhook” bo‘limi bo‘yicha
   HTTPS domen/reverse proxy tayyorlang. `.env` da `USE_WEBHOOK=true`, haqiqiy
   `WEBHOOK_URL`, yangi tasodifiy `WEBHOOK_SECRET` qo‘ying. Proxy hostdagi
   `127.0.0.1:8080` ga yo‘naltirsin; Compose ichida host `0.0.0.0`, port 8080.
   `WEBHOOK_PORT` tashqi mahalliy portni o‘zgartiradi. Maxfiy sarlavha saqlansin.
   `docker compose -p oqibat up -d --force-recreate bot` faqat shu botni yangilaydi.
   Oddiy polling uchun domen/TLS yoki ochiq kiruvchi port kerak emas.

### Zaxira nusxa, yangilash va qaytarish

Compose `backups` xizmati ishga tushganda bir nusxa, keyin har 86 400 soniyada
(24 soatda) yangi nusxa oladi. UTC nomli `oqibat-*.dump` fayllar `./backups` da,
faqat oxirgi 14 kun saqlanadi. Bu 14 dona fayl degani emas: bir kunda qo‘shimcha
nusxa olish mumkin. `scripts/backup.sh` PostgreSQL 16 klientida custom format,
no-owner/no-acl bilan yozadi, katalogini tekshiradi, keyin atomik nomlaydi. Faqat
muvaffaqiyatdan so‘ng o‘zining eski dump fayllarini tozalaydi. Crashdan qolgan
o‘zining yashirin vaqtinchalik fayllari ham 14 kundan
so‘ng muvaffaqiyatli backup paytida tozalanadi. Xatoda avvalgi nusxa
saqlanadi; keyingi kundalik urinish jurnalda ko‘rinadi. Birinchi nusxa bazaning
o‘sha paytdagi holati, yangi o‘rnatishda migratsiyadan keyin ham qo‘lda nusxa oling.
Papka shaxsiy ma’lumotli: serverda faqat mas’ul operator o‘qisin, boshqa himoyalangan
joyga ham ko‘chiring. Mahalliy nusxa server yo‘qolishidan himoya qilmaydi.

Quyidagi PowerShell misolida baza/foydalanuvchi `oqibat`; o‘zgartirgan bo‘lsangiz
moslang. Nusxada foydalanuvchi ma'lumotlari bor; uni himoyalangan boshqa joyga ko‘chiring.
Binary nusxani PowerShell `>` orqali o‘tkazmaymiz:

```powershell
docker compose -p oqibat up -d db backups
docker compose -p oqibat exec -T backups sh /scripts/backup.sh
$backupName = (Get-ChildItem .\backups -Filter 'oqibat-*.dump' | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
docker compose -p oqibat logs --tail 30 backups
docker compose -p oqibat stop bot
git pull --ff-only
docker compose -p oqibat build bot
docker compose -p oqibat run --rm bot alembic upgrade head
docker compose -p oqibat run --rm bot python -m bot --check
docker compose -p oqibat up -d bot
```

Tiklashni avval **yangi bo‘sh** bazada sinang, ishlayotgan bazani o‘chirmang:

```powershell
docker compose -p oqibat cp (Join-Path .\backups $backupName) db:/tmp/oqibat-restore.dump
docker compose -p oqibat exec -T db createdb -U oqibat -T template0 oqibat_restore_test
docker compose -p oqibat exec -T db pg_restore -U oqibat -d oqibat_restore_test --no-owner --no-acl --exit-on-error /tmp/oqibat-restore.dump
```

Bir xil tiklash nomini qayta ishlatmang. Kodni qaytarishdan oldin migratsiya eski
kodga mosligini Claude bilan tekshiring; avtomatik downgrade qilmang. Baza o‘zgargan
bo‘lsa, nusxani alohida bazaga tiklash va URL ni almashtirish rejasi kerak. Bu qo‘llanma
SQLite dan ishlab turgan PostgreSQL ga ma'lumot ko‘chirishni amalga oshirmaydi.

`pg_restore` custom dump uchun; bu SQL matn fayli emas. `--clean` bilan ishlayotgan
bazani tozalamang. Tekshiruv bazasida `/top`/hisoblar yoki kerakli jadvallarni
tekshirib, tiklash natijasini qayd eting. `backups` xizmati logida `backup_status=ok`
va fayl nomi bo‘lsin; `failed` bo‘lsa shu paytdagi PostgreSQL xatosini tekshiring.
systemd yo‘lini tanlasangiz alohida rejalashtirilgan backup ham sozlashingiz kerak;
ushbu avtomatlashtirish Compose xizmatida berilgan, host timer o‘rnatilmagan.

Jurnalda `ERROR`, `Traceback`, `retry_after` va besh daqiqalik `queue_length`,
`updates_per_minute`, `last_tick_duration_ms` ni tekshiring. Navbat doim o‘sayotgan
bo‘lsa ko‘proq guruh qo‘shishni to‘xtating; ayniqsa `queue_length > 1000` bo‘lsa
Claude qayd etgan heap tekshiruvini o‘lchang. Bir serverda 10,000 guruh ishlashi hali
haqiqiy yuk ostida isbotlanmagan. Faol o‘yinlar paytida yangilashdan saqlaning:
Mafia restartda bekor qilinadi, xotiradagi yuborish navbati saqlanmaydi.

### Linux serverda systemd (Compose o‘rniga)

Bu bo‘limdagi buyruqlar Linux server terminali uchun; Windows mahalliy ishga
tushirish yuqoridagi PowerShell bo‘limida. Python 3.12 va alohida PostgreSQL bazasi
oldindan tayyor bo‘lsin. Faqat shu bot uchun yangi `oqibat` tizim foydalanuvchisi
va `/opt/oqibat-bot` papkasini yarating; mavjud boshqa xizmatlarni o‘zgartirmang.

```bash
sudo useradd --system --user-group --home-dir /opt/oqibat-bot --shell /usr/sbin/nologin oqibat
sudo git clone https://github.com/sabdur4hmonov/oqibat-bot.git /opt/oqibat-bot
sudo chown -R oqibat:oqibat /opt/oqibat-bot
cd /opt/oqibat-bot
sudo -u oqibat python3.12 -m venv .venv
sudo -u oqibat .venv/bin/python -m pip install -r requirements.txt
sudo -u oqibat cp .env.example .env
sudo chmod 600 .env
sudo -u oqibat nano .env
```

`ENVIRONMENT=production`, `DATABASE_URL=postgresql+asyncpg://...`, pool 15 va haqiqiy
bot qiymatlarini kiriting. Compose ishlatilmasa POSTGRES_* qiymatlari bazani yaratmaydi;
URL da haqiqiy PostgreSQL hisobini yozing. URL paroli maxsus belgili bo‘lsa URL-encode
qiling. Oddiy URL-safe hex parol osonroq. systemd EnvironmentFile uchun oddiy
`KEY=value` qatorlaridan foydalaning, shell buyruqlari/qiymat almashtirish yozmang.

```bash
sudo -u oqibat .venv/bin/alembic upgrade head
sudo -u oqibat .venv/bin/python -m bot --check
sudo -u oqibat .venv/bin/python scripts/check_env.py
sudo install -m 644 deploy/oqibat-bot.service /etc/systemd/system/oqibat-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now oqibat-bot.service
sudo systemctl status oqibat-bot.service
sudo journalctl -u oqibat-bot.service -n 100 --no-pager
```

Xizmat faqat bot foydalanuvchisida, PostgreSQL bilan ishlaydi; `/opt/oqibat-bot`
xizmat vaqtida yozishdan himoyalangan. `sudo systemctl stop oqibat-bot.service`
to‘xtatadi. Yangilashdan oldin shu xizmatni to‘xtating, PostgreSQL nusxasini oling,
shu papkada kod/kutubxonalarni yangilang, tekshiring va xizmatni qayta yoqing.
Unit misoli berildi; haqiqiy systemd serverida ishlashi hali tekshirilmagan.

### Ixtiyoriy PostgreSQL tekshiruvi (faqat bo‘sh sinov bazasi)

`tests/test_postgres_integration.py` migratsiyadan oldin baza bo‘shligini tekshiradi.
Faqat mahalliy `127.0.0.1`/`localhost` va `oqibat_verify_` bilan boshlanuvchi yangi
baza nomini qabul qiladi; mavjud jadvalli bazaga tegmaydi. Har tekshiruvga yangi baza:

```powershell
$env:OQIBAT_TEST_DATABASE_URL = 'postgresql+asyncpg://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/oqibat_verify_new'
python -m pytest tests/test_postgres_integration.py -q
Remove-Item Env:OQIBAT_TEST_DATABASE_URL
```

Sinov o‘z bazasida jadvallar/namunalar yaratadi, o‘zi o‘chirmaydi. Ishlab turgan
baza URL ini bermang. Bu parametrsiz odatdagi pytest PostgreSQL sinovini o‘tkazib
yuboradi. Haqiqiy Telegram, TLS webhook, systemd va 10,000 guruh yuki alohida tekshiriladi.

Rasmiy qo‘llanmalar: [Compose loyiha nomlari](https://docs.docker.com/compose/how-tos/environment-variables/envvars/),
[PostgreSQL nusxa/tiklash](https://www.postgresql.org/docs/16/backup-dump.html),
[systemd xizmat muhiti](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html).

### Telegram Mini App (ixtiyoriy, faqat ko‘rish uchun)

Ilovada profil, guruhning oylik/barcha vaqt reytingi, shaxsiy yutuqlar va qoidalar bor.
Ilovani ochish rozilik bermaydi, ball yozmaydi, o‘yin yoki sozlamani o‘zgartirmaydi.
Mafia rollari va o‘yin holati API orqali berilmaydi. Guruh ro‘yxati faqat bot biladigan
faol a’zoliklardan tuziladi; Telegram barcha guruhlarni ro‘yxat qilib bermaydi.

1. O‘zingiz boshqaradigan domen/subdomen tayyorlang, masalan `bot.sizning-domen.uz`.
   DNS ni bot ishlaydigan serverga yo‘naltiring. Domeningiz uchun haqiqiy HTTPS
   sertifikatini sozlang; Telegram uchun `http://localhost` havolasi yaramaydi.
2. `.env` da `WEBAPP_URL=https://bot.sizning-domen.uz/webapp` yozing. Mahalliy oddiy
   polling uchun bo‘sh qoldiring. `WEBHOOK_HOST=127.0.0.1`, `WEBHOOK_PORT=8080`
   bilan reverse proxy shu lokal portga yo‘nalsin. Compose ichida mavjud
   `WEBHOOK_HOST=0.0.0.0` qiymatini saqlang; tashqariga faqat reverse proxy ochilsin.
3. Reverse proxy `/webapp` va `/webapp/…` yo‘llarini o‘zgartirmasdan shu portga
   uzatsin. `X-Telegram-Init-Data` sarlavhasini saqlasin, uni jurnalga yozmasin;
   `/webapp/api/` javoblarini keshlamasin. Alohida frontend jarayoni yoki build kerak emas.
   Pollingda bot shu portni o‘zi ochadi; webhook rejimida Mini App mavjud aiohttp
   serveriga qo‘shiladi. Webhook yo‘li `/webapp` bilan boshlanmasin.
4. `alembic upgrade head`, `python -m bot --check`, keyin `python -m bot` ni bajaring.
   HTTPS manzil ochilsin. Oddiy brauzerda profil o‘rniga Telegram ichidan ochish
   so‘ralishi to‘g‘ri: haqiqiy tasdiqlov faqat Telegramdan keladi.
5. BotFather da o‘z botingiz profilini tanlang, **Bot Settings → Configure Mini App**
   (yoki **Main Mini App**) orqali asosiy Mini App ni yoqing va shu HTTPS manzilni
   kiriting. Telegram mijoziga qarab menyu nomi farq qilishi mumkin. Bot profilidagi
   ilovani ochish tugmasini tekshiring. Ixtiyoriy shaxsiy menyu tugmasi uchun
   `/setmenubutton` dan foydalanish mumkin; bu asosiy Mini App sozlamasi o‘rnini bosmaydi.
6. Shaxsiy chatda `/start` yoki `/help` → “Ilovani ochish” tugmasi `web_app` bo‘lsin.
   Guruhda `/help` shu tugmani `https://t.me/BOT_USERNAME?startapp=<chat_id>` orqali
   asosiy ilovaga ochadi. Guruh ichida `web_app` turi ishlatilmaydi.
7. Guruh a’zosi bilan mavsum/barcha vaqtni, yutuqlarni, yorug‘/qorong‘i mavzuni
   tekshiring. Guruhdan chiqqach uning sahifasi rad etilsin. 24 soatdan so‘ng ilovani
   botdan qayta oching. Guruh ro‘yxatda bo‘lmasa o‘sha guruhdagi `/help` havolasini oching.

Har JSON so‘rovda xom `initData` `X-Telegram-Init-Data` sarlavhasida keladi. Server
bot-token usulidagi HMAC-SHA256 ni, 24 soatlik muddatni va ko‘pi bilan 30 soniya
oldinga vaqt farqini tekshiradi. Imzodagi foydalanuvchi ID ishlatiladi; URL dagi
`user_id`, `startapp` yoki `initDataUnsafe` ruxsat bermaydi. Guruh sahifasida har safar
Telegram `getChatMember` bilan joriy a’zolik tekshiriladi; bot admin bo‘lishi kerak.
Bir vaqtning o‘zida ko‘pi bilan beshta API so‘rovi, har biri ko‘pi bilan o‘n soniya;
Telegram band bo‘lsa keyinroq qayta urinish xabari chiqadi. Ilova javoblari saqlanmaydi.
Haqiqiy domen/TLS, BotFather va Telegram mobil/desktop sinovlari egasi tomonidan
bajariladi; ushbu ish davomida hech narsa serverga joylanmagan.

Rasmiy manbalar: [Mini App tasdiqlovini tekshirish](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app),
[asosiy Mini App](https://core.telegram.org/bots/webapps#launching-the-main-mini-app),
[shaxsiy inline tugmalar](https://core.telegram.org/bots/webapps#inline-keyboard-mini-apps).

### Matn banklarini tekshirish

Olti bank uchun shakl, misollar va yozish qoidalari [CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md)
da. Virtual muhitda, loyiha papkasida:

```powershell
python scripts/validate_content.py
```

Har `data/*.json` faylning element soni, tuzilma/uzunlik va takroriy key/matn xatolari
chiqadi. `$LASTEXITCODE` 0 bo‘lsa shakl to‘g‘ri, 1 bo‘lsa tuzatish kerak. .env,
Telegram yoki baza kerak emas; fayllar o‘zgarmaydi. Hozirgi uchta namuna katta,
ko‘rib chiqilgan kontent banki o‘rnini bosmaydi. Matn o‘zgarsa botni qayta ishga tushiring.

### Tosh–qaychi–qog‘oz (/tqq)

Avval botni to‘xtating va bazadan nusxa oling. Yangi koddan keyin virtual muhitda:

```powershell
alembic upgrade head
python -m bot --check
python -m bot
```

1. Guruhda bot admin bo‘lsin; ikkala odam `/qoshilish` bilan qo‘shilsin.
2. `/tqq` yoki `/toshqaychiqogoz` yuboring. Muayyan odamning xabariga javoban
   yuborsangiz, faqat o‘sha odam qabul qiladi. Ochiq o‘yinni boshqa qo‘shilgan a’zo oladi.
3. 90 soniyada qabul qiling. Keyingi 60 soniyada har kim Tosh, Qaychi yoki Qog‘ozni
   bitta tugma bilan tanlaydi. Birinchi tanlov qulflanadi; boshqalarga faqat
   “tanladi” holati ko‘rinadi. Ikkalasi tanlagach, ikkala tanlov va natija ochiladi.
4. Tosh qaychini, qaychi qog‘ozni, qog‘oz toshni yutadi. Bir raund: g‘olibga +2,
   durangda ball yo‘q. Yana o‘ynash uchun yangi `/tqq` yuboring.
5. Boshlovchi yoki admin `/stop` bilan bekor qiladi. Vaqt tugashi, bir ishtirokchining
   chiqishi, bot qayta yoqilishi yoki guruh superguruhga ko‘chishi o‘yinni ballsiz bekor qiladi.
   Boshqa asosiy o‘yin ketayotgan bo‘lsa, tugashini kuting; zar dueli alohida qoladi.

G‘olib kartalari yoqilgan bo‘lsa odatdagi rasm ham keladi; o‘chiq bo‘lsa matn yetarli.
Tanlov uchun shaxsiy chatni ochish shart emas. Telefonlarda haqiqiy Telegram sinovi
hali alohida bajariladi; hech qanday yangi token, server yoki kutubxona kerak emas.

Migratsiya mavjud o‘yin/vazifa bog‘lanishlarini saqlaydi. SQLite da ota jadvalni
qayta yaratishda faqat migratsiya ulanishida tashqi kalit tekshiruvi vaqtincha
to‘xtatiladi, yakunda bog‘lanishlar tekshiriladi va yoqiladi; bot ulanishlarida
tekshiruv doim yoqilgan. RPS tarixli bazani eski sxemaga qaytarish ma’lumot yo‘qotmaslik
uchun rad etiladi. [Alembic rasmiy batch qo‘llanmasi](https://alembic.sqlalchemy.org/en/latest/batch.html#dealing-with-referencing-foreign-keys)
shu SQLite jadval-almashtirish cheklovini tushuntiradi. O‘zgarish oldidan nusxa oling.

### Son topish va tezkor matematika

Yangi koddan oldin botni to‘xtating, bazadan nusxa oling; virtual muhitda
`alembic upgrade head`, `python -m bot --check`, keyin `python -m bot` bajaring.
`/oyinlar` shaxsiy chatda ham, guruhda ham barcha to‘qqiz o‘yin ro‘yxatini ko‘rsatadi.
Guruhda bot admin, o‘yinchilar esa `/qoshilish` bilan qo‘shilgan bo‘lsin.

- `/sontop`: 1–100 orasidagi son. **O‘yin xabariga javob** qilib faqat butun son
  yuboring; oddiy yozishma hisoblanmaydi. Bot “kattaroq/kichikroq” deb oraliqni
  toraytiradi. 15 ta qabul qilingan urinish va 3 daqiqa bor. Har bir odam o‘z
  urinishlari orasida kamida 3 soniya kutsin. Birinchi topuvchiga +3, topilmasa
  ball yo‘q. Takror/eski/uzatilgan yoki oraliqdan tashqari javob hisoblanmaydi.
- `/matematika`: qo‘shish, ayirish va ko‘paytirishdan 5 savol, har birida 4 tugma.
  Savol yetkazilgandan keyin 20 soniya, har odamga bir urinish. Noto‘g‘ri javob
  faqat o‘sha odamga popup bo‘ladi. Birinchi to‘g‘ri javobga +2, keyingi savolga
  o‘tiladi; vaqt tugasa javob ochilib, keyingisi chiqadi. Oxirida jami ballar va
  yoqilgan bo‘lsa karta ko‘rinadi. Yakun uchun qo‘shimcha ball yozilmaydi.

Son topishda 3 daqiqa va matematikadagi 20 soniya xabar yetkazilgach boshlanadi.
Yetkazish 90 soniyada bajarilmasa o‘yin to‘xtaydi. Matematikada bitta savolga
500 ta odamgacha urinish qabul qilinadi. Bir vaqtda bitta asosiy o‘yin; `/stop`
ni boshlovchi yoki admin ishlatadi. Boshlovchi chiqsa, bot qayta yoqilsa yoki guruh
ko‘chsa davom ettirilmaydi. Oldin yozilgan matematika ballari saqlanadi; qolgan
odamning chiqishi butun o‘yinni to‘xtatmaydi. Shaxsiy ma’lumotlarni o‘chirish
buyrug‘i avvalgidek tegishli o‘yin holatini tozalaydi.

Yangi kutubxona, haqiqiy token yoki kontent banki kerak emas. Savollar koddagi
cheklangan matematik amallardan tuziladi. Haqiqiy Telegram va serverdagi yuk
sinovi alohida; ushbu qo‘shimcha hech narsani serverga joylamaydi.

### HTTPS bilan ishga tushirish: Caddy profili (17-bosqich)

Quyidagi ishlar egasining serveri va domenida keyin bajariladi; ushbu ishlab chiqish
jarayonida domen ulanmagan yoki xizmat joylanmagan. Misoldagi **oqibat.com** ni
**o‘zingiz boshqaradigan domen** bilan almashtiring; nomning o‘zi sizga tegishli degani emas.

1. Domen DNS boshqaruvida `A` yozuvini serverning haqiqiy ochiq IPv4 manziliga
   qo‘ying. Agar `AAAA` bo‘lsa IPv6 ham shu serverga kelishi kerak; ishlamaydigan
   IPv6 yozuvini domen egasi tuzatsin. DNS yangilanishini kuting.
2. Server/cloud firewall va kerak bo‘lsa routerda **TCP 80 va 443** ni Caddyga
   oching. SSH va boshqa loyihalar qoidalarini saqlang; band 80/443 ni egasiz
   to‘xtatmang. PostgreSQL porti ommaga ochilmaydi, botning 8080 porti hostda
   faqat 127.0.0.1 ga bog‘langan.
3. Avvalgi Compose sozlamalarini to‘ldiring; `.env` da:

   ```dotenv
   DOMAIN=oqibat.com
   ENVIRONMENT=production
   USE_WEBHOOK=true
   WEBHOOK_URL=https://oqibat.com/telegram
   WEBAPP_URL=https://oqibat.com/webapp
   WEBHOOK_SECRET=BU_YERGA_YANGI_TASODIFIY_MAXFIY_QIYMAT
   ```

   Haqiqiy BOT_TOKEN/BOT_USERNAME/OWNER_ID va tasodifiy POSTGRES_PASSWORD ham kerak.
   `python -c "import secrets; print(secrets.token_urlsafe(32))"` bilan yangi webhook
   secret yarating va uni `.env` ga yozing. DOMAIN da protokol, port yoki yo‘l bo‘lmasin.
   Caddy faqat DOMAIN oladi; bot tokeni/baza paroli Caddy muhitiga berilmaydi.
4. Faqat o‘z loyihangiz nomi bilan config tekshiring, oldin Caddy va bazani yoqing:

   ```powershell
   docker compose -p oqibat --profile https config --quiet
   docker compose -p oqibat --profile https up -d caddy db
   docker compose -p oqibat --profile https logs --tail 50 caddy
   ```

   Caddy domen uchun sertifikatni avtomatik oladi va HTTP ni HTTPS ga yo‘naltiradi.
   Sertifikat olingani/tuzatilgani jurnalda ko‘rinsin. Shu payt bot hali yoqilmagan
   bo‘lsa upstream 502 tabiiy; sertifikat xatosini 502 bilan aralashtirmang.
   `caddy_data`/`caddy_config` doimiy hajmlari sertifikat/kalitni saqlaydi; ularni
   ko‘r-ko‘rona o‘chirmang. Caddy sertifikati uchun ham 80/443 ochiq qolsin.
5. HTTPS tayyor bo‘lgach bitta bot jarayoni va backupni yoqing:

   ```powershell
   docker compose -p oqibat --profile https up -d --build bot backups
   docker compose -p oqibat ps
   docker compose -p oqibat logs --tail 100 bot
   ```

   Bot avval migratsiya, keyin listener va webhook ro‘yxatini tayyorlaydi. Caddy
   yo‘lni o‘zgartirmay bot:8080 ga uzatadi: `/telegram`, `/webapp`, `/webapp/*`,
   `/healthz`. Boshqa backend yo‘li yo‘q bo‘lsa 404; statik disk fayllari ochilmaydi.
   Webhook va initData sarlavhalari saqlanadi; Caddy log filtri ulardagi maxfiy
   qiymatlarni chiqarib tashlaydi. Access log alohida yoqilmagan.
6. Sog‘liq va Telegramning haqiqiy webhook yozuvini tekshiring:

   ```powershell
   Invoke-RestMethod https://oqibat.com/healthz
   docker compose -p oqibat exec -T bot python scripts/webhook_info.py
   ```

   `/healthz` 200/`status=ok`, yangi `last_tick_age_seconds`, navbat uzunligini ko‘rsatsin.
   Skript aynan **getWebhookInfo** chaqiradi: URL sozlangan rejimga mos, kutayotgan
   yangilanishlar kamayadi/0 bo‘ladi. Oxirgi xato vaqti eski qayd bo‘lishi mumkin;
   u yangilanayotgani va bot logini tekshiring. Token buyruq argumenti yoki javobda
   chiqmaydi, raw Telegram error matni ham chop etilmaydi. Noto‘g‘ri URL yoki aloqa
   xatosida exit 1. Webhookni tekshirish uchun `getUpdates` ni parallel ishga tushirmang.
7. Botga /start yuboring, guruhda /help, ilovada profilni oching. BotFather Main Mini
   App URL ini yuqoridagi Mini App bo‘limi bo‘yicha sozlang. HTTPS GET ochilishi
   webhook POST/header tasdig‘i o‘rnini bosmaydi; LIVE_TEST.md qadamlarini bajaring.

Oddiy polling uchun `--profile https` ni yoqmang va `USE_WEBHOOK=false` qoldiring.
Webhookdan pollingga o‘tish Telegramdagi webhookni pending update’larni tashlamay
olib tashlaydi. Caddy ishlayotgan bo‘lsa uni to‘xtatish alohida qaror; profilni
keyingi buyruqdan olib tashlash ishlayotgan Caddy konteynerini avtomatik o‘chirmaydi.

### Sog‘liq va egaga xato xabarlari

`/healthz` webhook yoki Mini App serverida bor. Production pollingda Mini App bo‘sh
bo‘lsa ham sog‘liq uchun HTTP listener 8080 da ishlaydi; mahalliy development polling
Mini App bo‘lmasa HTTP server ochmaydi. Birinchi tugagan tick bo‘lmaguncha yoki
oxirgi tugagan tick 120 soniyadan eski bo‘lsa HTTP 503, aks holda 200. Baza so‘rovi
qilinmaydi, maxfiy ma’lumot berilmaydi. Tick ichidagi alohida muvaffaqiyatsiz hook
backoff bilan tugashi mumkin; health scheduler ishlayotganini, hamma yuborish
muvaffaqiyatli ekanini kafolatlamaydi. Navbat/egaga alert/logni birga tekshiring.

Docker stdlib probe’ni har 30 soniyada ishlatadi, boshlanishga 120 soniya beradi;
uch marta yomon tekshiruv `unhealthy` qiladi. Dockerning o‘zi faqat unhealthy sabab
konteynerni avtomatik qayta yoqmaydi. `docker compose ps` va bot logini ko‘ring.

OWNER_ID egasi botning shaxsiy chatida avval **Start** bosgan bo‘lsin. Ushlanmagan
handler/scheduler/fon xatolari va o‘n daqiqada uch takror Sender muvaffaqiyatsizligi
qisqa DM beradi. Oddiy blocked-user holati normal reachability sifatida qayd etiladi.
Birinchi alert darhol, qolganlari birlashtiriladi: ko‘pi bilan 10 daqiqada bitta
alert; navbat yoki Telegram javobi kechiksa interval tasdiq/xato qaytganidan keyin ham to‘liq saqlanadi. Xulosa
oxirgi xato turi, belgilangan joy, chat ID, UTC vaqt, jami hodisalar va qo‘shilgan
xatolar sonini (jami−1) ko‘rsatadi. Exception matni, foydalanuvchi xabari, token,
parol yoki initData yuborilmaydi. Owner bloklagan/aloqa yo‘q bo‘lsa alert botni
buzmaydi va o‘zidan yangi alert hosil qilmaydi. Alertlar xotirada; restartda
birlashtirilgan hisob yo‘qolishi mumkin, bu durable queue emas.

Rasmiy qo‘llanmalar: [Caddy automatic HTTPS](https://caddyserver.com/docs/quick-starts/reverse-proxy),
[Caddy environment](https://caddyserver.com/docs/caddyfile/concepts#environment-variables),
[Telegram getWebhookInfo](https://core.telegram.org/bots/api#getwebhookinfo),
[PostgreSQL custom dump](https://www.postgresql.org/docs/16/app-pgdump.html).

### 17-bosqichning mahalliy testlari

Oddiy testlar uchun `requirements-dev.txt` kerak; production Docker obrazida
pytest/ruff yo‘q. Backup shell testlari Windowsda ham alohida tarmoqsiz klient
konteynerida ishlaydi. Docker va keshlangan `postgres:16-alpine` kerak:

```powershell
$env:OQIBAT_TEST_BACKUP_DOCKER = '1'
python -m pytest tests/test_backup.py tests/test_production.py -q
Remove-Item Env:OQIBAT_TEST_BACKUP_DOCKER
```

Parametrsiz backup konteyner testlari skip bo‘ladi; ular haqiqiy loyiha bazasini
ochmaydi. PostgreSQL integratsiyasi yuqoridagi alohida yangi/bo‘sh/local baza
parametri bilan tekshiriladi. Kundalik 24 soatlik devor-soat sinovi, haqiqiy
DNS/sertifikat chiqarish va real Telegram ishlashi egasining muhitida alohida qoladi.

### Shaxsiy o‘yinlar va fon o‘yini (18–21-bosqichlar)

Barcha yangi o‘yinlarga guruhdagi lobby havolasini bosib shaxsiy Start orqali
rozilik bilan qo‘shiling. Mafia bilan birga **bir odamga faqat bitta faol shaxsiy
kontekst** ruxsat. `/yashirin` bitta alohida fon joyini oladi; qolganlari asosiy
joydan foydalanadi. Fon va asosiy o‘yin birga yursa, kerakli doskaga `/stop` bilan
javob bering. Boshlovchi yoki admin to‘xtatadi.

| Buyruq | Odam / lobby | Shaxsiy topshiriq va natija |
|---|---|---|
| `/yashirin`, `/fosh` | 3–20 / 5 daqiqa | Boshlovchi 2/6/24 soatni tanlaydi (odatda 24). Har kim bitta nishon va faol ovchilar orasida yagona so‘z oladi. Nishon yangi guruh matni/izohida so‘zni aytsa +10, ko‘pi bilan 3 muvaffaqiyat. `/fosh` gumondagi ovchining xabariga javoban: to‘g‘ri +5 va so‘z yangilanadi; xato −2, 1 soat kutish; jami 3 gumon. |
| `/kimaytdi` | 4–12 / 3 daqiqa | Bir xil savolga 5 daqiqada bitta matn (<=300 belgi). Javoblar anonim, 30 soniya taxmin, keyin muallif. To‘g‘ri topgan har odam +3; hech kim topmasa muallif +3. |
| `/telefon` | 4–10 / 3 daqiqa | Navbat 2 daqiqa, ovoz <=30 soniya; keyingiga faqat oxirgi ovoz. Oxirgi odam matn yozadi (<=300 belgi). Yakunda asl jumla, matn va ovozlar ketma-ket ochiladi; yashirilmagan material topshirgan har odam +3. |
| `/eslaysizmi` | 3–10 / 5 daqiqa | 5 daqiqada bitta photo, ixtiyoriy izoh <=300 belgi. Guruhga spoiler bilan; 30 soniyadan keyin yuboruvchi va izoh ochiladi. Topuvchiga +3, kamida bir topuvchi bo‘lsa yuboruvchiga +2. |

Yashirin uchun bankdagi turli so‘zlar soni o‘yinchilar sonidan kamida bitta ko‘p
bo‘lsin. Uchta namuna bilan uch kishilik o‘yin boshlanmaydi: CONTENT_GUIDE bo‘yicha
kamida to‘rtinchi so‘zni yozing. So‘z yangi guruh matni yoki captionida token bilan
moslashadi; 4+ harfli so‘zga qo‘shimcha mumkin (`palov` → `palovni`, `palovdan`).
Uzatilgan/tahrirlangan xabarlar yutuq bermaydi. Ketgan odamdan keyin aylana tuzatiladi,
uchdan kam qolsa bekor bo‘ladi. Oddiy xabarlar uchun SQL kerak emas.

Kim/Surat o‘yinida har odam bir marta taxmin qiladi, o‘z materialiga ovoz bera olmaydi.
Hech kim topshirmasa bekor; ayrimlar yuborgan bo‘lsa kelgan materiallar o‘ynaladi.
Telefon navbatida vaqt tugasa yoki shaxsiy xabar yetmasa odam o‘tkaziladi va oxirgi
ovoz saqlanadi. Hali ovoz yo‘q bo‘lsa keyingi so‘zlovchiga jumla beriladi; oxirgi
matn yo‘q bo‘lsa bu aytiladi. Ovoz/rasm fayli yuklab olinmaydi: Telegram file_id,
rozilik bilan berilgan matn/izoh va cheklangan o‘yin ma’lumotlari JSON holatda saqlanadi.

Shaxsiy materialda link, @eslatma, forward, tahrir va noto‘g‘ri media qabul qilinmaydi.
Har guruh materialida **admin uchun yashirish** tugmasi bor. Botning o‘chirish huquqi
bo‘lsa xabar o‘chadi; matn aks holda belgilanadi. Media uchun shu huquq o‘yin boshida
va chiqarishda tekshiriladi. Huquq yo‘qolsa yoki Telegram o‘chirishni rad etsa, izohni
belgilash ovoz/rasmni olib tashlamaydi — admin qo‘lda o‘chirsin. Yashirilgan material
muallif bonusi olmaydi; berilgan bonus alohida qarshi ledger yozuvi bilan bir marta
bekor bo‘ladi. Topuvchining boshqa bali saqlanadi. Migratsiyadan oldingi material
ID lari yangi guruhda qayta ishlatilmaydi; eski tarixni admin alohida boshqaradi.

Stop/restart/migratsiya/shaxsiy ma’lumotni o‘chirish va asosiy shaxsiy o‘yinlarda
/chiqish o‘yinni bekor qiladi. Oldin tasdiqlangan raund ballari takrorlanmaydi;
Telefon yakuniy reveal tugaguncha ball bermaydi. Botdan oldin yetkazilgan Telegram
xabarlari hamda tashqi backupni `/malumotlarimni_ochir` o‘chirmaydi.

Yangilash va mahalliy tekshirish (PowerShell):

```powershell
python -m pip install -r requirements-dev.txt
alembic upgrade head
python scripts/validate_content.py
python -m pytest
ruff check .
python -m bot --check
```

Jonli ro‘yxat: [docs/LIVE_TEST.md](docs/LIVE_TEST.md). Eslaysizmi/Yashirin uch kishi
bilan; Kim/Telefon uchun to‘rtinchi odam kerak. Haqiqiy Telegram, ovoz ijrosi,
rasm spoilerlari va server quvvati alohida tekshiriladi. Bu bosqichlar deploy qilmaydi,
review ZIP ham yaratmaydi.
