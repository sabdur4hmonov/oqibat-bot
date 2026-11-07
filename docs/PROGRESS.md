# Progress log

## Current status
- Current phase: Phase 2 implemented and locally verified; proceeding to Phase 3 under the owner's explicit request to continue through remaining PLAN phases.
- Last updated: 2026-11-07 (Asia/Tashkent)

## Review notes from Claude
<!-- Sardorbek pastes Claude's review notes here. Codex: apply all unchecked items before the next phase,
     then tick them [x] and say how each was handled in your phase entry. -->

## Phase entries
<!-- Codex: add one entry per phase, newest at the bottom, using this template. -->

<!--
### Phase N — <name> — <YYYY-MM-DD>
- Status: done | partial
- Commit(s): <hash> <message>
- What was built:
- Files added/changed:
- Tests: `pytest` result (N passed), `ruff check .` result
- Acceptance criteria: list each one from PLAN.md with ✅ / ❌ and a note
- Deviations from PLAN.md and why:
- Open questions / decisions needed:
- Known issues / TODO:
- Manual test steps (Uzbek, simple, step by step in Telegram):
-->

### Phase 0 — Foundation — 2026-11-07
- Status: partial — implementation and local checks are complete; real Telegram startup and manual acceptance checks need the owner's local `.env` credentials.
- Commit(s): `dec87fc` `docs: add plan and agent rules`; `5e38d61` `phase-0: foundation`. This entry is recorded in a following documentation commit.
- What was built:
  - Imported `C:\Users\user\Downloads\oqibat-bot.zip` (newest matching archive) into the repository. Clone encountered an existing `.git` directory; the requested `git init` fallback was used, with `main` and the specified GitHub origin. The planning commit was pushed successfully.
  - Read AGENTS.md, PLAN.md and this log fully. There were no unresolved Claude review notes to apply.
  - Python 3.12 environment, dependencies from PLAN section 3, ignored local secrets/databases, validated configuration with hidden credentials, and Windows PowerShell instructions.
  - All eight tables from PLAN section 5, UTC timestamp handling, SQLite foreign keys, constraints and indexes, and initial Alembic revision `4bd30211b7ec`. Points remain a ledger; no mutable balance was added.
  - Long-polling entrypoint with all five mandatory update types, HTML parse mode, private `/start` and `/help`, slogan, Instagram footer, add-to-group deep link, escaped user names, and private-user reachability persistence.
  - Separate private/group command registration, a global update error handler, logging with credential redaction, and the shared sender. It waits/retries once on rate limits, marks blocked users or inaccessible groups inactive, and contains send/database failures while allowing cancellation.
  - Six documented UTF-8 JSON bank schemas and three sample items in each (18 total). Normalization foundation handles apostrophe variants, Uzbek Cyrillic, punctuation and whitespace without Telegram.
  - Folder layout from PLAN section 4. Later-phase modules contain docstrings only; no group onboarding, scheduler, challenge logic or games were started.
- Files added/changed:
  - `.env.example`, `.gitignore`, `requirements.txt`, `pyproject.toml`, `README.md`.
  - `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/4bd30211b7ec_initial_foundation_schema.py`.
  - `bot/__main__.py`, `bot/config.py`, `bot/texts.py`, database models/session/repositories, private and error handlers, keyboards, sender and utilities; documentation-only placeholders in the remaining planned folders.
  - `data/README.md`, all six JSON files, `tests/` and this progress log. AGENTS.md and PLAN.md were preserved.
- Tests:
  - Python 3.12.13; `pytest`: **56 passed**; `ruff check .`: **all checks passed**.
  - `alembic upgrade head`: passed against the local SQLite database and clean temporary databases. Repeating the upgrade is safe; `alembic check` reports **No new upgrade operations detected**.
  - Tests cover config validation/secret handling, normalized matching, content schemas, UTC round trips, foreign keys and uniqueness, sender failure/retry behavior, escaped private replies, command scopes, mandatory updates, global errors and startup.
  - `python -m bot --check`: passed in a subprocess against a migrated temporary database using a clearly fake test token, with no network calls. Normal startup through command registration/polling handoff passed with a local fake Telegram session. No real Telegram sends were made.
  - The user's explicitly ordered initial docs-only setup commit preceded tool installation: `pytest` and `ruff` were unavailable then. Both checks were installed and passed before the Phase 0 implementation commit, and rerun before committing this entry.
- Acceptance criteria:
  - ✅ Repository skeleton, requirements, `.env.example`, `.gitignore`, config and all initial models: implemented.
  - ✅ First Alembic migration creates the database; migration/model consistency verified.
  - ✅ Safe sender, global error handler and logging: implemented and tested, including a forbidden response after a rate-limit retry.
  - ✅ Private `/start` and `/help` with Uzbek text, slogan, footer, escaped names and add-to-group button: verified through aiogram's dispatcher using a fake transport.
  - ✅ Command registration in separate private/group scopes, README setup/run steps and six documented sample banks: implemented.
  - ✅ Config and normalization tests: passing.
  - ❌ Real `python -m bot` long polling and real Telegram `/start` acceptance: not verified, because no valid BOT_TOKEN or other owner-specific `.env` settings were supplied. The offline check and mocked startup do not establish live authentication/connectivity.
- Deviations from PLAN.md and why:
  - Added `python -m bot --check` to verify configuration and schema offline without making Telegram calls. It does not replace normal polling or a live acceptance test.
  - Group commands are registered as an empty scope until their handlers exist. Only implemented private commands are advertised; the full group command list remains for later phases.
  - The plan leaves `daily_time` and `daily_enabled` defaults unspecified. Small defaults are 09:00 local and enabled, documented in README. No scheduler runs in Phase 0.
  - Interpreted “empty-but-valid ... with 3 sample items each” as three illustrative objects per bank, with empty arrays documented as valid for future loaders.
  - No additional project dependencies beyond PLAN section 3. `uv` was used only to install the required Python version and prepare the local environment.
- Open questions / decisions needed:
  - Confirm the 09:00 daily-time default before the scheduler phase, if a different default is desired. No architecture decision is blocked.
  - Owner must set the real bot token, username, Instagram handle and numeric OWNER_ID locally to perform the live checks. Do not paste secrets into this log or commit them.
- Known issues / TODO:
  - Phase 0 remains partial only because live Telegram checks have not been performed. PostgreSQL has not been tested against a live server; that verification remains in Phase 9 as planned.
  - Production content, group onboarding, all scheduled activity and games remain unimplemented, intentionally outside Phase 0.
  - No Phase 1 work was started. Stop here after pushing this entry.
- Manual test steps (Uzbek, simple, step by step in Telegram):
  1. README dagi PowerShell ko‘rsatmalarini bajaring. `.env` fayliga o‘z bot tokeningiz, bot nomi, Instagram nomi va Telegram foydalanuvchi ID raqamingizni yozing. Tokenni hech kimga yubormang.
  2. Virtual muhitni yoqing. `alembic upgrade head`, keyin `python -m bot --check` buyrug‘ini bajaring. Baza tayyorligi haqida xabar chiqishi kerak.
  3. `python -m bot` buyrug‘ini bajaring. PowerShell oynasini ochiq qoldiring.
  4. Telegramda botning shaxsiy chatini oching. **Start** tugmasini bosing yoki `/start` yuboring.
  5. Ismingiz bilan salomlashuv, “Guruhda oqibat bo‘lsin”, “Muallif: @...” va “Botni guruhingizga qo‘shing” tugmasi chiqqanini tekshiring.
  6. `/help` yuboring. O‘zbekcha yordam, shior, muallif manzili va shu tugma chiqishi kerak.
  7. Guruhga qo‘shish tugmasini bosing. Telegram guruh tanlash va administrator huquqlarini berish oynasini ochishi kerak. Hozir guruh o‘yinlari va qo‘shilish tugmalari ishlamaydi; ular keyingi bosqichlar uchun.
  8. PowerShell oynasida **Ctrl+C** bosing. Bot to‘xtashi kerak. `python -m bot` bilan qayta ishga tushirib, `/start` ni yana tekshiring.

### Phase 0.5 — Scale foundation — 2026-11-07
- Status: done for local phase acceptance; real Telegram, public TLS webhook and live PostgreSQL checks remain unverified without credentials/server access.
- Commit(s): `f104496` `phase-0.5: scale queue scheduling and runtime services`; this log is committed separately.
- What was built:
  - PLAN section 10 records all requested scale rules for later phases; section 8 now includes Phase 0.5. No unresolved Claude review notes were present.
  - One bounded async priority queue shared by the runtime, rolling 25 attempts/second globally and 18/minute per chat, at most 25 in flight, priority GAME > CHALLENGE > BULK, retry once, chat/global pauses, direct callback answers, safe cancellation and forbidden handling.
  - Stable daily 0–900 second and weekly 0–3599 second BLAKE2 spreading, local-time recurrence converted to UTC, three indexed chat due timestamps, and both requested composite deadline indexes in new migration `6d500d9c95f9`. The old migration was not edited.
  - Scheduler infrastructure queries at most 500 indexed due rows per kind. Job kinds progress concurrently, with 25 callbacks per kind; successful chat jobs conditionally bulk-update their next time. Unimplemented/failed hooks retain due state; no product hooks were registered in this phase.
  - Message activity/name buffering with 60-second transactional bulk flushes and shutdown flush; no SQL on ordinary incoming messages. Unknown groups are not created and opt-in flags are preserved. Failed flushes retain newer observations. Forbidden private sends cannot be overwritten by an older in-flight activity flush.
  - Startup-loaded pending challenge set and commit-synchronized repository; admin cache with 10-minute TTL, coalesced fetches, membership invalidation/refresh and stale-fetch protection; shared per-chat game/session locks and repository writes.
  - Production PostgreSQL mode with 10–20 connections (default 15), no overflow; optional authenticated aiohttp webhook with env settings and polling default. Transport changes preserve pending updates. Runtime owns queue, flush, tick and metric task lifecycle.
  - Five-minute INFO metrics for queue length, rolling updates/minute and last tick duration; isolated 5,000-chat simulation and Windows documentation.
- Files added/changed: `docs/PLAN.md`, `.env.example`, `README.md`, `requirements.txt`, entrypoint/config/private handlers, DB models/session and challenge/game repositories, new migration, scale services, `scripts/simulate_load.py`, existing tests and six scale test modules.
- Tests: `pytest -q`: **91 passed**, no warnings; `ruff check .`: **all checks passed**. `alembic upgrade head` and `alembic check`: passed, **No new upgrade operations detected**. Offline module startup and mocked polling startup still pass.
- Load result: 5,000 fake chats, ten real scheduler ticks, 500 daily + 500 challenge + 500 weekly items per tick. **15,000 due items processed**, zero due daily rows remaining; tick **164.366–412.688 ms**, mean **238.250 ms**, using an isolated temporary SQLite DB and fake successful work hooks. Zero Telegram requests. These results do not prove production delivery capacity.
- Acceptance criteria:
  - ✅ PLAN rules, prioritized limiter, callback bypass, explicit retry scopes and stable spreading implemented and tested with a fake clock.
  - ✅ New UTC/index migration, indexed bounded queries, recurrence and query-plan index use verified.
  - ✅ Incoming-message path has zero SQL; 1,000 repeated messages coalesce into two table upserts. Chunked 350-user flush, opt-in preservation and failed-flush recovery verified.
  - ✅ Pending-cache startup/commit synchronization, admin TTL/coalescing/invalidation races, concurrent game state changes and metrics verified.
  - ✅ PostgreSQL-required production config and bounded pool tested without connecting; local webhook rejects missing/wrong secrets and accepts a valid update; runtime cleanup tested.
  - ✅ Isolated 5,000-chat simulation runs, prints counts/timings and respects 500-per-kind batches.
  - ❌ Live PostgreSQL/public webhook/Telegram capacity not measured. Docker CLI exists but its daemon is not running; no database server or real bot credentials were supplied.
- Deviations from PLAN.md and why:
  - Telegram's retry response has no global/chat scope indicator. Ambiguous 429s conservatively pause globally; known chat-specific callers can choose `retry_scope="chat"`. This is explicit in PLAN and README rather than guessing a Telegram feature.
  - SQL cannot portably upsert users and memberships in one statement. One flush transaction executes one upsert per table per 100-row chunk to respect SQLite limits; never one write per message.
  - Added `ENVIRONMENT`, `DB_POOL_SIZE` and `WEBHOOK_HOST` alongside requested webhook variables. Declared `aiohttp` directly because the owner explicitly requested it; it was already an aiogram dependency.
  - Due timestamps are NULL until that chat is initialized/configured. Later onboarding/settings call `initialize_schedule` for that chat; no all-chat initialization scan was introduced.
- Open questions / decisions needed: no blocking architecture question. Single process per server is required for these in-memory coordination primitives. Production capacity must be measured on the actual server before claiming support for 10,000 active groups.
- Known issues / TODO: caches/buffer/queue are not crash-durable; the last minute of activity may be lost on a crash. Actual post/challenge/game hooks remain for their planned phases. The owner explicitly authorized continuing through the remaining PLAN phases, superseding the earlier stop-after-0.5 instruction.
- Manual test steps (Uzbek, simple):
  1. Virtual muhitni yoqing. `alembic upgrade head`, keyin `python -m bot --check` buyrug‘ini bajaring.
  2. `python scripts/simulate_load.py --ticks 10` buyrug‘ini bajaring. `fake_chats=5000` va oxirida `total_due_items_processed=15000`, `remaining_due_daily=0` chiqishi kerak. Har bir tick uchun 500 tadan uch turdagi ish va vaqt ko‘rsatiladi. Bu haqiqiy guruhlarga xabar yubormaydi.
  3. `.env` dagi haqiqiy bot ma'lumotlarini kiriting. Mahalliy tekshiruvda `USE_WEBHOOK=false` qoldiring, `python -m bot` bilan ishga tushiring va Telegramda `/start`, `/help` ni tekshiring.
  4. Bot besh daqiqa ishlaganda PowerShell oynasida `queue_length`, `updates_per_minute`, `last_tick_duration_ms` chiqishini tekshiring. Oddiy guruh xabarlari bazaga har safar yozilmaydi; faollik taxminan bir daqiqada saqlanadi.
  5. Webhookni faqat HTTPS domen va server tayyor bo‘lganda README bo‘yicha sozlang. `WEBHOOK_SECRET` ni oshkor qilmang. Hozirgi bosqichda hali guruh o‘yinlari yo‘q.

### Phase 1 — Group onboarding & opt-in — 2026-11-07
- Status: done for implementation/local acceptance; live Telegram acceptance remains pending local credentials.
- Commit(s): `e8da522` `phase-1: group onboarding consent and admin settings`; progress is committed separately.
- What was built: group welcome/admin-rights guidance via `my_chat_member`, removal/re-addition state, opt-in button and `/qoshilish`, `/chiqish`, join/leave tracking, cached admin helper, admin-only inline `/sozlamalar` for all ten configurable policy fields. Reply prompts validate timezone/HH:MM/threshold input and expire after five minutes. Ordinary message activity still uses the 60-second buffer. Onboarding/settings initialize indexed due timestamps for that chat.
- Files added/changed: group/settings handlers and keyboards, group repository, settings validation/prompt service, admin helpers, runtime wiring, command registration and Uzbek texts, README, group tests and private command-registration expectation.
- Tests: `pytest -q`: **126 passed**; `ruff check .`: **all checks passed**. Mock Telegram integration covers non-admin add → promote → remove → re-add, opt-in persistence/opt-out, non-admin popup denial, admin settings edits, escaped prompt names and reply input. Pure tests cover membership states, every setting choice, invalid inputs, prompt ownership/expiry. No schema change.
- Acceptance criteria:
  - ✅ Adding/promoting the bot welcomes the group with the opt-in button; missing rights show Uzbek instructions; removal and re-addition persist correctly in mocked update flows.
  - ✅ Opt-in registers membership; opt-out clears consent and cancels pending tasks without penalty.
  - ✅ Non-admin settings callbacks show a private denial popup; admin callbacks/replies update policy and recompute due times. All ten configurable fields are exposed; Telegram-managed metadata is not editable.
  - ✅ Message activity has no per-message SQL; the existing buffer/cache/limiter rules remain in use.
  - ❌ Real test-group add/click/remove/re-add has not been exercised without a real bot token.
- Deviations from PLAN.md and why: leaving a group clears opt-in so rejoining requires fresh consent; numeric kick thresholds accept 1–100 as a small validation bound. Explicit commands and membership/settings transitions persist immediately; ordinary messages are buffered. Button opt-in confirmation uses a private callback popup to avoid a group-message burst.
- Open questions / decisions needed: none blocking; the owner explicitly authorized continuing through all remaining planned phases.
- Known issues / TODO: scheduled posts/tasks/games are not implemented in this phase. Reply-prompt state is memory-only and must be reopened after a restart. Live Telegram verification remains required.
- Manual test steps (Uzbek, simple):
  1. Botni ishga tushiring va sinov guruhiga oddiy a'zo qilib qo‘shing. Administrator qilish bo‘yicha ko‘rsatma chiqishi kerak.
  2. Botni administrator qiling. “O‘yinga qo‘shilish” tugmasi chiqishi kerak. Tugmani bosing; qo‘shilganingiz haqida shaxsiy oynacha chiqadi.
  3. `/chiqish`, keyin `/qoshilish` yuboring. Chiqish va qayta qo‘shilish ishlashini tekshiring.
  4. Guruh administratori sifatida `/sozlamalar` yuboring. Vazifalar soni va jazo turini o‘zgartiring. Kunlik vaqtni tanlab, bot savoliga `22:15` deb javob yozing.
  5. Oddiy a'zo shu menyu tugmasini bossin: faqat administrator o‘zgartirishi mumkinligi haqida oynacha chiqishi, qiymat o‘zgarmasligi kerak.
  6. Botni guruhdan olib tashlab, qayta administrator qilib qo‘shing. Salomlashuv va qo‘shilish tugmasi yana chiqishi kerak.

### Phase 2 — Scheduler & daily messages — 2026-11-07
- Status: done for implementation/local acceptance; live Telegram checks remain pending credentials.
- Commit(s): `4bd0e89` `phase-2: daily posts content rotation and check-ins`; progress committed separately.
- What was built: validated UTF-8 content loader for all six banks (empty through 3,000+ items), no-repeat/oldest-used selection, escaped `{group}` rendering, indexed daily scheduler hook, quiet-hour deferral, durable per-date reservation/delivery audit, cached participant/post lookup and buffered daily +1 check-ins. Same-second replies and replies received while awaiting the send response are handled. Startup checks every modeled column.
- Files added/changed: content, daily, check-in/participation services, UTC/quiet utilities, runtime/group cache wiring, scheduler deferral support, Uzbek rendering, README and tests. New migration `7f8830fef1b4` adds post delivery metadata and unique point-event references; old migrations preserved.
- Tests: `pytest -q`: **142 passed**; `ruff check .`: **all checks passed**; `alembic upgrade head` and `alembic check`: passed, no schema drift. Tests cover post-once/restart, failed-send audit, quiet deferral, immediate replies, check-in deduplication after restart, empty/3,000-item banks, malformed content, rotation and quiet boundaries.
- Acceptance criteria:
  - ✅ A due daily job sends one escaped message; a second call or restarted service does not repost for that date.
  - ✅ Daily check-in gives +1 once per member/local date, backed by a unique ledger reference, including after a restart.
  - ✅ No-repeat content usage and quiet hours work; quiet daily jobs move to quiet end rather than being dropped or repeatedly selected.
  - ✅ Incoming detection uses memory only; check-ins flush in batches every 60 seconds and on clean shutdown.
  - ❌ Real two-minute-ahead Telegram timing not exercised without credentials. Section 10 adds 0–15 minutes of deterministic spreading, so manual waits must include that offset and the 30-second tick interval.
- Deviations from PLAN.md and why:
  - Added delivery status/message/time/content metadata and point-event uniqueness via a new migration, needed for auditable restart behavior and check-in boundaries.
  - Telegram offers no send idempotency key. Reservation is committed before send; reserved/failed deliveries are not automatically replayed after an ambiguous error/crash. This prevents duplicates but can leave a day's post missing. README explains the tradeoff; this is not a claim of exactly-once delivery under every network failure.
  - Check-ins apply to opted-in active members and are buffered with unique references, preserving the zero-query ordinary-message path. A crash can lose an unflushed check-in; a later message that day may qualify again. Future stats commands flush before reading totals.
- Open questions / decisions needed: none blocking; ambiguous reserved/failed post rows need operator review rather than blind resend.
- Known issues / TODO: no live token/server tests; production content remains owner-authored; challenges and game hooks remain in their next phases. `/men` and `/top` arrive in Phase 3.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring va botni ishga tushiring. Sinov guruhida administrator bo‘lishi, o‘zingiz `/qoshilish` bilan qo‘shilgan bo‘lishingiz kerak.
  2. `/sozlamalar` da kunlik xabarni yoqing va vaqtini ikki daqiqa oldinga qo‘ying. 0–15 daqiqalik tarqatish oralig‘i qo‘shiladi; xabar 2–17 daqiqa va yana 30 soniyagacha kechroq kelishi mumkin.
  3. Bitta kunlik xabar kelishini, guruh nomi to‘g‘ri ko‘rinishini tekshiring. Botni qayta ishga tushiring: shu kun uchun yana xabar yuborilmasligi kerak.
  4. Kunlik xabardan keyin bir nechta xabar yozing. Bir daqiqa ichida faqat bitta +1 hodisasi saqlanadi; `/men` ko‘rinishi keyingi bosqichda qo‘shiladi.
  5. Tinch vaqt ichiga tushadigan vaqtni tanlang: kunlik xabar tinch vaqt tugaguncha yuborilmasligi kerak.
