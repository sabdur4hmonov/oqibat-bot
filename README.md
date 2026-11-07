# Oqibat Bot

**Guruhda oqibat bo‘lsin.** Telegram group engagement bot for Uzbekistan.
Python 3.12, aiogram 3, SQLAlchemy 2 async, Alembic. Phase 0 implements the foundation
and private `/start` and `/help`. Phase 0.5 adds shared scale services. Phase 1 implements group onboarding,
member consent and admin settings; Phase 2 adds daily posts, content rotation, quiet hours
and daily check-in points. Phase 3 adds challenges, point ledgers, penalties and leaderboards.
Phase 4 adds dice duels, five-question quizzes, and would-you-rather polls. Phase 5 adds Krokodil; Phase 6 adds Haqiqat yoki jasorat. Phase 7 adds Mafia; Phase 8 adds weekly summaries and full help. Phase 9 adds shareable result cards and deployment examples.

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
| `RESULT_CARDS_ENABLED` | `true` (default) for winner/weekly PNG cards; `false` keeps text results |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose database settings; use a fresh random hex password |

The example token is a placeholder. Do not commit `.env` or send the token in chat.
The username is checked against Telegram's `getMe` before polling. Secrets are
hidden in configuration representations/errors and redacted in runtime logs.

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

Town wins with no mafia; mafia wins at parity. Winning-side members earn +10 and
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
with the local Monday date as the weekly key. As with daily posts, ambiguous
reserved/failed sends are not replayed automatically; a day's/week's delivery may
be missing after a crash, while duplicate prevention is preserved. Large outages
produce one report for the stored due week, not a burst for every missed week.
Chat/date indexes bound point and resolved-task reporting queries. All scheduling
still uses the indexed 500-row batches, never a scan of chats.

Private and group `/help` now list every implemented command and game timing, plus
the footer and add-to-group button. Routine game/task/daily messages have no footer.

### Result cards (Phase 9)

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
   docker compose -p oqibat up -d bot
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

Quyidagi PowerShell misolida baza/foydalanuvchi `oqibat`; o‘zgartirgan bo‘lsangiz
moslang. Nusxada foydalanuvchi ma'lumotlari bor; uni himoyalangan boshqa joyga ko‘chiring.
Binary nusxani PowerShell `>` orqali o‘tkazmaymiz:

```powershell
New-Item -ItemType Directory -Force .\backups
$backupName = 'oqibat-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump'
docker compose -p oqibat exec -T db pg_dump -U oqibat -d oqibat -Fc -f /tmp/oqibat-backup.dump
docker compose -p oqibat cp db:/tmp/oqibat-backup.dump (Join-Path .\backups $backupName)
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
docker compose -p oqibat exec -T db pg_restore -U oqibat -d oqibat_restore_test --no-owner --exit-on-error /tmp/oqibat-restore.dump
```

Bir xil tiklash nomini qayta ishlatmang. Kodni qaytarishdan oldin migratsiya eski
kodga mosligini Claude bilan tekshiring; avtomatik downgrade qilmang. Baza o‘zgargan
bo‘lsa, nusxani alohida bazaga tiklash va URL ni almashtirish rejasi kerak. Bu qo‘llanma
SQLite dan ishlab turgan PostgreSQL ga ma'lumot ko‘chirishni amalga oshirmaydi.

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
