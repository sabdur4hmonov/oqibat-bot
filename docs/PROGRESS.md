# Progress log

## Current status
- Current phase: Phase 13 implemented and locally verified; proceeding sequentially to Phase 14 content tooling.
- Last updated: 2026-11-09 (Asia/Tashkent)

## Review notes from Claude
<!-- Sardorbek pastes Claude's review notes here. Codex: apply all unchecked items before the next phase,
     then tick them [x] and say how each was handled in your phase entry. -->

- [x] Handle group→supergroup migration atomically across chats/memberships/point_events/challenges/content_usage/scheduled_posts/game_sessions; leave the old chat inactive. Catch and handle TelegramMigrateToChat in Sender. Add tests.
- [x] Run game + expire deadlines in their own loop and separate lock, independent of bulk batches and outbound pauses. Test a slow daily batch against a game deadline.
- [x] Treat `sender_chat.id == chat.id` anonymous-admin messages as admin for `/sozlamalar` and admin-only commands.
- [x] Back off failing scheduled chats to `next_*_at = now + 10 min`, log it, and test it.
- [x] Use an accurate member-check-failed message for `/qoshilish`, not NEED_ADMIN.
- [x] Later note only: Sender._take_ready rescans chat-limited heaps; optimize if metrics show queue > 1000. No change requested now.

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

### Phase 3 — Challenges, points, penalties — 2026-11-07
- Status: done for implementation/local acceptance; live Telegram moderation remains unverified without credentials.
- Commit(s): `996ce79` `phase-3: challenges point ledger and safe penalties`; progress committed separately.
- What was built: pure weighted picker with active/opt-in eligibility and 24-hour fallback; scheduled/admin-forced challenges, escaped mentions and local deadlines, quiet-hour deadline extension, type/target/time/message-order completion, atomic status/streak/point ledger updates, expiry and all penalty modes, once-only debtor mentions, `/vazifa`, `/men`, `/top`. Pending type/deadline/message indexes keep unrelated messages free of SQL. All point constants from section 6.5 are defined for subsequent games.
- Files added/changed: challenge orchestration/repository/cache, picker/penalty/point services, challenge/stats handlers, runtime and command wiring, Uzbek texts/time helpers, daily debtor integration, README and tests. Migration `c1ba47fee0f6` adds one-pending-task-per-chat uniqueness and debtor announcement time; old migrations preserved.
- Tests: `pytest -q`: **167 passed**; `ruff check .`: **all checks passed**. `alembic upgrade head` and `alembic check`: passed, no drift. Tests include round-video +15, wrong user/kind rejection, concurrent duplicate completion, streak reset, points/off expiry, debtor text, uniqueness, picker/deadlines/points, admin/owner protection, stale-cache promotion protection, bot rights, supergroup capability, mute/kick timing and stats rendering. The assignment command cannot complete its own text task.
- Acceptance criteria:
  - ✅ Forced round-video task completes only for its assigned user and adds +15 exactly once in mocked Telegram integration.
  - ✅ Expiry resolves once, increments misses, applies the configured point policy, and supports mute/kick when permitted; completed tasks reset misses.
  - ✅ Administrators, the group creator and configured bot owner cannot be muted/kicked; target status is checked fresh immediately before the queued action. Missing owner configuration/permissions fail closed.
  - ✅ Pure picker, quiet/deadline, point-policy tests and `/men`/`/top` integration checks pass; all totals come from the ledger.
  - ❌ Real Telegram video/timeout/mute/kick tests are pending local credentials and a controlled test supergroup.
- Deviations from PLAN.md and why: `/vazifa` accepts optional Uzbek format aliases for predictable manual testing. Mute/kick are skipped in basic groups because Telegram supports restriction/unban semantics in supergroups. Kick uses ban→unban with `only_if_banned=True` and an automatic five-minute ban expiry as a failsafe if immediate unban fails. Deadlines are computed at assignment and extended out of quiet hours. No dependency or architecture change.
- Open questions / decisions needed: none blocking. Production moderation should be manually checked with consenting test accounts before enabling mute/kick in real groups.
- Known issues / TODO: bot credentials remain absent; no real moderation was attempted. Delivery failure cancels a newly assigned task without penalizing the user. Games are next; no Phase 4 code was included in this commit.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring, botni ishga tushiring, sinov superguruhida administrator va a'zolarni cheklash huquqini bering. Bir nechta sinov a'zosi `/qoshilish` yuborsin.
  2. Admin `/vazifa video` yuborsin. Tanlangan a'zo muddat tugashidan oldin dumaloq video yuborsin: tabrik va +15 chiqishi kerak. Boshqa a'zoning videosi vazifani bajarmasligi kerak.
  3. Tanlangan a'zo `/men` yuborsin, keyin guruhda `/top` ni tekshiring. Video takror yuborilganda yana +15 berilmasligi kerak.
  4. `/sozlamalar` da jazo turini `points` qiling. Sinov vazifasini muddatigacha bajarmang: −5 va keyingi kunlik xabarda qarzdor eslatmasi chiqishi kerak. `off` da ball ayirilmasligi kerak.
  5. Faqat rozilik bergan oddiy sinov a'zosi bilan `mute` yoki `kick` ni tekshiring. Administrator va egaga bu choralar qo‘llanmasligi kerak. `kick` dan keyin havola orqali qaytish mumkin bo‘lishi kerak.
  6. Tinch vaqt ichida `/vazifa` yuboring: yangi vazifa berilmasligi kerak. Muddati tinch vaqtga tushgan vazifa tinch vaqt tugaguncha uzaytiriladi.


### Pre-Phase 4 — Claude review fixes — 2026-11-07
- Status: done for implementation/local verification; all six review notes above are acknowledged and ticked.
- Commit(s): this entry accompanies `review: migrate supergroups and isolate deadline progression`.
- What was built: atomic movement of all seven requested tables, persistent inactive source aliases, synchronized memory caches and outbound destination rewriting; explicit Sender TelegramMigrateToChat retry; independent one-second game/expiry loop with a separate lock and tracked outbound effects; anonymous-admin authorization for own-group messages; ten-minute failed-hook backoff with logs; accurate membership-check failure text. The heap optimization is recorded for later only and was not implemented.
- Files added/changed: migration repositories/services and new Alembic revision `7d9a7f721c61`, shared locks/sender/runtime/scheduler, daily/challenge/point paths, group/settings handlers, texts, README and review tests.
- Tests: `pytest -q`: **184 passed**; `ruff check .`: **all checks passed**. Offline startup/migration consistency checks remain covered by the suite. New tests cover every moved table, rollback, duplicate updates, destination stub collisions, opt-out preservation, point deduplication, cache rekeying, low new-group message IDs, Sender migration retry, both migration service updates, slow bulk work, globally paused notifications, all three failed-hook kinds, anonymous admin commands/replies and join-check errors.
- Acceptance criteria: ✅ all actionable Claude notes implemented and tested; ✅ deferred queue note recorded without speculative optimization. ❌ Real Telegram supergroup conversion has not been exercised without bot credentials.
- Deviations from PLAN.md and why: added persistent migration aliases and message-origin IDs in a new migration so restarts and changed message-number scopes remain safe. If both IDs already contain data, opt-out wins, duplicate identical point references are merged, conflicting point amounts abort atomically, and duplicate active tasks/main games are cancelled without a penalty. Deadline state commits before asynchronous notification/moderation; Telegram pauses may delay delivery but not deadline resolution. Missing hooks remain untouched; failed hooks back off ten minutes.
- Open questions / decisions needed: none blocking. Sender heap optimization remains conditional on measured queue growth over 1,000.
- Known issues / TODO: queued notifications are process-local and may be lost on a crash; audit/point/deadline state is durable. Live migration and moderation checks remain pending credentials.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring, keyin botni ishga tushiring.
  2. Sinov guruhida `/qoshilish` yuboring, vazifa oling va ball to‘plang. Guruhni superguruhga aylantiring. `/men` va `/sozlamalar` da oldingi ball va sozlamalar saqlanganini tekshiring.
  3. Oldingi vazifani yangi superguruhda bajaring: u bir marta hisoblanishi kerak. Botni qayta ishga tushiring va ballni yana tekshiring.
  4. Administratorning anonim rejimini yoqing. `/sozlamalar` va `/vazifa` ishlashi kerak; oddiy a'zo uchun admin amallari yopiq qoladi.
  5. Telegram a'zolik tekshiruvini bajara olmasa, `/qoshilish` administrator huquqi haqida noto‘g‘ri xabar emas, a'zolikni tekshirib bo‘lmagani haqida xabar berishi kerak.


### Phase 4 — Easy games — 2026-11-07
- Status: done for implementation/local acceptance; live Telegram play remains pending credentials.
- Commit(s): this entry accompanies `phase-4: dice duels quiz rounds and choice polls`; prior review fixes were pushed as `8eb6e56`.
- What was built: open/reply-targeted 90-second dice lobbies, starter emoji selection (🎲/🎯/🎳), bot-only rolls, four-second animation deadline, tie rerolls and atomic +2 award; five non-anonymous 30-second quiz polls with first-answer scoring (+3 and first-correct +2), instant-response buffering, one edited scoreboard and durable ledger references; 60-second non-anonymous regular choice polls; shared game cache, transactional revision-checked transitions and starter/admin/anonymous-admin `/stop`. Game deadline hooks commit state before tracked outbound effects, retaining Claude's independent-loop fix.
- Files added/changed: pure easy-game engines, game repository/cache/hub/orchestrator and handlers, runtime/command/text wiring, content draw helper, README and tests. New migration `31b65b0e9d42` adds `wyr` to the game constraint and follows the review migration; old migrations preserved.
- Tests: `pytest -q`: **194 passed**; `ruff check .`: **all checks passed**. Alembic upgrade and schema check pass. Tests cover ranges/ties/scoring, duplicate button spam, reply-target protection, all five quiz rounds and totals, early poll answers, consent checks, stop permissions, anonymous stop, cancellation before award, creation races, ambiguous restart recovery and deadline progress during a global send pause. Offline startup remains covered by the full suite.
- Acceptance criteria: ✅ each game runs end-to-end through mocked aiogram updates; ✅ duel/quiz points recorded once; ✅ `/stop` closes active polls and cancels state; ❌ live test-group play has not been performed without a bot token.
- Deviations from PLAN.md and why: a regular choice poll lasts 60 seconds and earns no points (the plan leaves this unspecified). Track it as a `wyr` session so one-main-game and stop behavior apply. A duel lobby lasts 90 seconds; each starter may have one active duel. The first quiz answer per question is final, and polls disable revoting. Three sample questions necessarily repeat over five rounds; no additional production content was invented. Ambiguous in-flight poll/dice sends cancel on restart; established question/animation state resumes.
- Open questions / decisions needed: none blocking; live interaction and real content remain owner checks.
- Known issues / TODO: outbound delivery can be delayed by Telegram limits; no state lock or deadline loop waits for it. A crash can lose pending notifications, but committed game state/points remain durable.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring. Botni ishga tushiring, sinov guruhida admin qiling. Kamida ikki a'zo `/qoshilish` yuborsin.
  2. `/duel` yuboring. Boshlovchi 🎲, 🎯 yoki 🎳 ni tanlasin, ikkinchi a'zo duelni qabul qilsin. Bot ikkala zarni tashlaydi; natija animatsiyadan keyin chiqadi. Teng bo‘lsa qayta tashlaydi, g‘olibga +2 beriladi.
  3. Bir a'zoning xabariga javoban `/duel` yuboring: faqat o‘sha a'zo qabul qila olishi kerak.
  4. `/viktorina` yuboring. Besh savolga javob bering, har biriga 30 soniya ajratiladi. Yakunda o‘sha natija xabari yangilanadi; `/men` orqali ballni tekshiring.
  5. `/tanla` yuboring. Ochiq so‘rovnomada ovoz bering; u bir daqiqadan so‘ng yopiladi.
  6. O‘yin boshlovchisi yoki admin `/stop` yuborsin: o‘yin to‘xtashi kerak. Oddiy boshqa a'zo buni qila olmasligi kerak. Duel xabariga javoban `/stop` yuborib, aynan shu duelni tanlang.


### Phase 5 — Krokodil — 2026-11-07
- Status: done for implementation/local acceptance; live three-person Telegram game remains pending credentials.
- Commit(s): this entry accompanies `phase-5: private Krokodil words timed rounds and scoring`; Phase 4 was pushed as `8ec22b6`.
- What was built: private host-only word popups, two skips per round, normalized exact guessing (apostrophes/Cyrillic), ten three-minute rounds, guesser-to-host handoff, random opted-in timeout host, revealed previous word, +5/+3 awards, host reveal −3/new word, one edited board and shared stop/recovery. Ordinary unrelated messages need no SQL. Matching messages are revision-checked, deduplicated by message ID and atomically scored. Added per-chat participant indexing for host selection without scanning other groups; migration rekeys that index and resets changed message-number scopes. Game writes cancel safely when the bot loses admin/active status.
- Files added/changed: pure Krokodil engine, orchestration and handlers, popup-safe content validation, participant/cache/migration helpers, runtime/text wiring, README and tests. No schema change or new dependency.
- Tests: `pytest -q`: **206 passed**; `ruff check .`: **all checks passed**. Includes a ten-round three-person simulated game (80 total points, 20 ledger events), host-only popups, two-skip limit without extending deadlines, normalized variants, host reveal/deduplication, timeout/stop, zero-query unrelated guesses, and no award after admin removal. Existing migration/startup tests remain passing.
- Acceptance criteria: ✅ complete three-person flow through mocked Telegram updates; ✅ apostrophe/Cyrillic matching; ✅ points, ten-round end, timer and stop; ❌ live Telegram testing is pending a real token.
- Deviations from PLAN.md and why: minimum two opted-in players; the starter hosts first. Skips and host word leaks preserve the original round deadline. Host leaks are detected within longer text too, while guesses require the full normalized word. Words are capped at 100 characters to fit private popups. These are small validation/flow choices; production content was not expanded.
- Open questions / decisions needed: none blocking.
- Known issues / TODO: three sample words repeat after rotation; the owner/Claude should supply the production bank. Send delays can postpone board delivery, while persisted round deadlines continue independently.
- Manual test steps (Uzbek, simple):
  1. Botni ishga tushiring. Uch a'zo `/qoshilish` yuborsin, bittasi `/krokodil` yuborsin.
  2. Boshlovchi “So‘zni ko‘rish” tugmasini bossin: so‘z faqat unga oynachada chiqadi. Boshqa a'zo bossa so‘z chiqmasligi kerak.
  3. Boshlovchi so‘zni yozmasdan tushuntirsin. Boshqa a'zo javobni yozsin: unga +5, boshlovchiga +3 beriladi, topgan a'zo keyingi boshlovchi bo‘ladi.
  4. `O‘zbekiston`, `O'zbekiston` va `Ўзбекистон` kabi yozuvlarni mos so‘z kelganda tekshiring.
  5. Bir turda so‘zni ikki marta almashtiring; uchinchisi rad etiladi. Boshlovchi so‘zni guruhga yozsa −3 va yangi so‘z bo‘lishi kerak.
  6. Bir turni uch daqiqa kuting: so‘z ochiladi va yangi boshlovchi tanlanadi. 10 turdan keyin o‘yin tugaydi; oldinroq `/stop` ham ishlaydi.


### Phase 6 — Haqiqat yoki jasorat — 2026-11-07
- Status: done for implementation/local acceptance; stopped here at the owner's explicit request. Phase 7 has not been started and waits for Claude's review of Phases 4–6.
- Commit(s): this entry accompanies `phase-6: truth dare and atomic refusal lifecycle`; Phase 5 was pushed as `2510f79`.
- What was built: `/hyj` with random opted-in or reply target; target-only choice/refusal buttons; truth question with 30-minute text/voice response and atomic +5; targeted dare through the existing typed challenge engine with a one-hour deadline and existing kind scores; atomic game/task/point resolution so completion, refusal and expiry cannot double-score. Refusal costs only −2 and cancels the dare without moderation. Target opt-out and `/stop` cancel safely. Deadline work remains independent of outbound waits; question-send recovery and bounded early-response buffering are included. Outbound board edits have a separate game-specific lock to prevent a delayed question edit overwriting a refusal/final result.
- Files added/changed: pure truth-answer validation, orchestration/handlers, shared challenge/game/group repositories and lifecycle caches, runtime/commands/texts, README and tests. New migration `e26b09e84d37` adds nullable indexed `challenges.game_session_id` with a foreign key; old migrations preserved. Migration handling also resets the truth message-number boundary in the new chat scope.
- Tests: `pytest -q`: **222 passed**; `ruff check .`: **all checks passed**. `alembic upgrade head` and `alembic check` pass with no schema drift. The full suite includes offline module startup and mocked polling startup; no real Telegram requests were made. Sixteen Phase 6 tests cover both truth response types, all four dare media/score kinds, random/reply selection, target authorization, deadline/message boundaries, pending-task conflict, mute/kick-mode refusal without moderation, completion/refusal and expiry/refusal races, transaction rollback, opt-out/stop cancellation and delayed-edit ordering.
- Acceptance criteria: ✅ truth and dare branches run end-to-end in mocked Telegram flows; ✅ only the target can choose/refuse; ✅ correct point amounts, cancellation and one outcome per task; ❌ live Telegram acceptance remains pending a real bot token.
- Deviations from PLAN.md and why: choice timeout is 90 seconds; truth/choice timeouts have no extra penalty. Unrefused dare expiry uses the existing configured challenge penalty, while an accepted refusal only costs −2 and cancels it. Dares obey the mandatory quiet-hour rules, including extending an ending inside quiet hours to quiet end. A durable task-to-game link is needed to make refusal/completion/expiry atomic and restart-safe. No new dependency or architecture redesign.
- Open questions / decisions needed: no blocking implementation question. Claude should review Phases 4–6 before the owner authorizes Phase 7.
- Known issues / TODO: real test-group behavior remains unverified without credentials. The three sample content items are illustrative; production content is still owner/Claude-authored. Outbound notifications are memory-only across a crash; task/game status and point events are durable. Phase 7 and all later phases remain untouched in this phase.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring, keyin botni ishga tushiring. Sinov guruhida bot admin bo‘lsin, a'zolar `/qoshilish` bilan qo‘shilsin.
  2. Bir a'zoning xabariga javoban `/hyj` yuboring. Faqat o‘sha a'zo “Haqiqat”, “Jasorat” yoki “Rad etish” tugmasini bosa olishi kerak. Boshqa a'zo bosganda rad javobi chiqadi.
  3. “Haqiqat”ni tanlang. 30 daqiqa ichida matn yoki ovozli javob yuboring: +5 bir marta beriladi. `/men` bilan tekshiring.
  4. Yangi `/hyj` da “Jasorat”ni tanlang. Tinch vaqt bo‘lmasin va boshqa vazifa kutilayotgan bo‘lmasin. Tanlangan a'zo kerakli video, ovoz, surat yoki matnni yuborsin; odatdagi vazifa ballari beriladi.
  5. Yangi jasoratda muddat tugashidan oldin “Rad etish”ni bosing. Faqat −2 bo‘lishi, vazifa bekor qilinishi va a'zo cheklanmasligi/chiqarilmasligi kerak. Tugmani qayta bosish yana ball ayirmaydi.
  6. `/stop` yoki tanlangan a'zoning `/chiqish` buyrug‘i o‘yin va vazifani jarimasiz bekor qilishi kerak.
  7. Haqiqatni javobsiz 30 daqiqa qoldiring: qo‘shimcha jarimasiz tugaydi. Jasoratni rad etmasdan muddatigacha bajarmasangiz, guruhning oddiy vazifa jazosi ishlaydi; buni faqat rozilik bergan sinov a'zolari bilan tekshiring.
  8. Shu bosqichdan keyin to‘xtaymiz. Claude 4–6-bosqichlarni ko‘rib chiqmaguncha Mafia boshlanmaydi.


### Phases 0–6 — Claude review and live-test preparation — 2026-11-07
- Status: done for preparation/local verification. No Phase 7 work was started; live Telegram testing remains for the owner and three-person test group.
- Commit(s): this entry accompanies `test: prepare Claude review and Uzbek live checks`; Phase 6 remains `3a5ce7b`.
- What was built:
  - Ran the requested `git archive --format=zip -o "..\oqibat-review.zip" HEAD` against Phase 6, outside the repository, and verified no `.env` was included. The archive is refreshed from the preparation commit after committing so Claude receives the checklist and checker too; the ZIP comment records its exact source commit. Location: `D:\Coding projects\oqibat-review.zip`. It is not committed.
  - `docs/LIVE_TEST.md`: 101 unchecked steps in simple Uzbek, each with an expected result, covering setup/BotFather/.env/owner ID, one group with three people, all implemented Phase 0–6 features, permissions/settings/quiet hours, daily points, all challenge and penalty modes, every game, restart/migration checks, scale tests, conditional PostgreSQL/webhook checks, log troubleshooting and a review report template. Slow real deadlines and optional server checks are clearly marked; Mafia and later features are excluded.
  - `scripts/check_env.py`: reads project-root configuration with normal environment overrides, validates token syntax/placeholders and settings, checks real getMe plus case-insensitive username match, checks DB connectivity and required tables/columns. Uzbek problem-specific messages live in `bot/texts.py`; credentials and raw exception values are not printed. Returns 0 on success, 1 on failure, 130 on cancellation. Network probes have timeouts; missing SQLite files are reported without creating them. It sends no messages and starts no bot/scheduler.
  - README links the checklist/checker and corrects stale descriptions of implemented games, commands and scheduler hooks.
- Files added/changed: `docs/LIVE_TEST.md`, `scripts/check_env.py`, `tests/test_check_env.py`, `bot/texts.py`, `README.md`, `docs/PROGRESS.md`. No dependency, schema or game behavior change.
- Tests: `pytest -q`: **254 passed** (32 checker tests added); `ruff check .`: **all checks passed**; `alembic check`: **no new upgrade operations detected**. All 11 PowerShell examples in LIVE_TEST parse successfully; all 101 checkboxes have an expected result. Archive inspected for excluded `.env`. Checker tests cover getMe success/error/timeout/rate limit, username mismatch, placeholder rejection, secret masking, actual temporary SQLite connectivity/schema, missing DB preservation, relative path resolution, DB failures/cleanup, env validation and CLI exit behavior.
- Acceptance criteria: ✅ review ZIP outside repo with no `.env`; ✅ full Uzbek live checklist; ✅ environment checker and local tests; ✅ committed/pushed preparation, then stop. ❌ No real Telegram authentication or three-person live test was performed: this checkout has no `.env`. Running the checker locally correctly reports the missing `.env` with setup instructions and exit code 1.
- Deviations from PLAN.md and why: owner-requested review/testing preparation only, not a new product phase. The checker additionally verifies schema readiness so a reachable but unmigrated database does not falsely pass. The archive is refreshed after the commit to include the new preparation files.
- Open questions / decisions needed: none for this task. Claude's review and owner-provided local credentials are still needed before live acceptance/Phase 7 authorization.
- Known issues / TODO: checklist items remain unchecked because real group tests have not run; PostgreSQL/webhook live checks need the corresponding server. The archive includes committed files only, not later local test notes or content edits.
- Manual test steps (Uzbek, simple):
  1. `docs/LIVE_TEST.md` ni oching, A/B/C ishtirokchilarni belgilang va 1-bo‘lim bo‘yicha bot hamda `.env` ni sozlang.
  2. Migratsiyani bajaring, keyin `.\.venv\Scripts\python.exe scripts\check_env.py` ni ishga tushiring. Barcha satrlar `[OK]`, chiqish kodi 0 bo‘lsin; `[X]` bo‘lsa undagi ko‘rsatmani bajaring.
  3. Botni jurnal bilan ishga tushiring. Uch kishilik sinov guruhida qadamlarni bajaring; faqat haqiqatan o‘tganlarini belgilang.
  4. Ishlamagan qadamning vaqtini va 11-bo‘limdagi jurnal parchasini yozing; token va `.env` ni ulashmang.
  5. `D:\Coding projects\oqibat-review.zip` va test natijalarini Claude ko‘rishi uchun tayyorlang. Phase 7 hozircha boshlanmaydi.


### Phase 7 — Mafia — 2026-11-07
- Status: implementation/local acceptance complete; live Telegram testing remains unverified without credentials. The owner explicitly authorized Phases 7–9 in sequence for this run, overriding the earlier phase stop/review gate.
- Commit(s): this entry accompanies `phase-7: Mafia engine private actions and bounded lifecycle`.
- What was built: pure role distribution, night/doctor/commissioner/day-vote/win/scoring logic; 90-second deep-link-only lobby; one active lobby/game reservation per user across chats; provisional role delivery with forbidden-recipient removal, group announcement and role recalculation before confirmation; mafia teammate names and private live tally; no-vote/no-kill; private role boards and one edited group board; session+round validation on every action, dead/wrong-context rejection, doctor self-save limit, one commissioner check/night; 20-round/60-minute draw caps; starter/admin stop and restart cancellation with private notices; opt-out/leave forfeits without further action/awards. State/points commit under the shared chat lock; deadline hooks dispatch tracked outbound effects and never await the send queue. All Mafia sends/edits/deletes use GAME priority.
- Files added/changed: `bot/games/mafia/`, Mafia orchestration/keyboards/handlers, deep-link private start, runtime/game cache synchronization, admin setting UI, texts, README/PLAN/LIVE_TEST, tests, new migration `ea783b4100c2`. The new chat setting defaults OFF; deletion checks the bot's delete right fresh. SQL error parameter logging is disabled to avoid leaking private role state. The missing-env CLI preflight now reports before importing the SDK, fixing a cold-start timeout found by the full suite.
- Tests: `pytest -q`: **282 passed**; `ruff check .`: **all checks passed**; `alembic upgrade head` and `alembic check`: passed, no schema drift. Pure scripted town/mafia wins plus 1,000 seeded random complete games check termination, valid winners, role distribution, no resurrection and rejected dead actions/votes. Mocked flows exercise both five-player winners and exact points, private checks/tallies, stale/foreign-context callbacks, cross-chat join races, forbidden role DMs (continue with five/cancel with four), stop/restart notices, optional deletion/right checks, migration registry/board rekeying, draw during preparation and independent deadlines during a global send pause. Alembic upgrade/schema check passed.
- Acceptance criteria: ✅ full five-player games reach town/mafia winners through mocked aiogram updates; ✅ dead players cannot act/vote; ✅ all requested extra rules implemented and locally tested; ❌ real Telegram five-person play remains unverified without a token. This does not block the offline implementation of the following phases.
- Deviations from PLAN.md and why: reservations include lobbies to prevent ambiguous concurrent private flows. Role proposals are explicitly provisional and all are discarded/recalculated after a forbidden recipient; actions activate only after every remaining recipient succeeds. Ambiguous non-forbidden delivery failures cancel safely. Lobby creation starts the 60-minute cap; a preparation-only draw earns no points. Opt-out/leave forfeits and excludes that user from game awards. Deletion is best effort and bounded to 5,000 pending deletions globally. No dependency or architecture change; one process remains mandatory.
- Open questions / decisions needed: no blocking implementation question. Public role/tally timing and permission behavior still need consenting live testers.
- Known issues / TODO: private notifications/queued edits are process-local and can be lost on a crash; restart cancels durable Mafia sessions. Real delivery may lag during Telegram pauses while state deadlines continue. Production capacity is not established by the local fuzz/simulation tests.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring. Kamida besh kishi sinov guruhida `/qoshilish` yuborsin. `/mafia` ni boshlang va har bir kishi havola orqali botning shaxsiy chatida Start qilsin.
  2. 90 soniyadan keyin rollar shaxsiy chatda tasdiqlansin. Mafia sheriklarini ko‘rsin; nishon tanlaganda ovoz hisobi faqat mafialarda yangilansin. Doktor va komissar o‘z tugmalarini sinasin.
  3. 60 soniya tun, 90 soniya muhokama, 60 soniya guruh ovozini tekshiring. Chiqqan odam va oldingi tur tugmalari ishlamasin; guruh doskasi qayta yuborilmasdan yangilansin.
  4. Olti kishidan biri boshlanish oldidan botni bloklasin: u ro‘yxatdan olinsin, besh kishi bilan rollar qayta hisoblansin. Beshdan biri bloklasa o‘yin bekor bo‘lsin.
  5. `/sozlamalar` dagi chiqqanlarning xabarini o‘chirish dastlab o‘chiq bo‘lsin. Faqat yoqilganda va botda o‘chirish huquqi bo‘lsa yangi xabarlar o‘chirilsin.
  6. G‘olib tomonga +10, tirik qolganlarga +3 ni `/men` bilan tekshiring. `/stop` va qayta yoqish o‘yinni bekor qilib, ishtirokchilarga shaxsiy xabar bersin. To‘liq qadamlar LIVE_TEST 13-bo‘limida.


### Phase 8 — Weekly summary & polish — 2026-11-07
- Status: implementation/local acceptance complete; live Sunday delivery remains unverified without credentials.
- Commit(s): this entry accompanies `phase-8: weekly summaries reporting indexes and complete help`; Phase 7 was pushed as `32b6e73`.
- What was built: registered weekly BULK hook using the existing indexed due scheduler; stable Sunday 20:00–21:00 spreading; per-week reservation/delivery audit; top five weekly point totals, most active member, completed/missed/current-pending challenges, slogan/footer/add-group button. Quiet hours defer delivery; Monday catch-up keeps the original week, and chat migration cannot change week identity through a changed hash offset. Full private/group help covers every implemented command, game timing and stop/opt-in rules, with appropriate footer/button. Query windows are chat/date bounded.
- Files added/changed: weekly reporting service, runtime hook, group help handler/texts, new reporting indexes in migration `b45a921b3120`, models, README/PLAN/LIVE_TEST and weekly tests. Old migrations preserved; no dependency change.
- Tests: `pytest -q`: **293 passed**; `ruff check .`: **all checks passed**; Alembic upgrade/check: passed, no drift. Eleven weekly tests cover timezone/week boundaries, distinct scored activity and top-five ordering, task counts, empty reports, indexed queries, post-once/restart, concurrent calls, Monday quiet deferral followed by a distinct next-week report, failed-send audit/backoff/no replay, full help/footer/buttons and migration with changed hash spreading. Offline startup and previous phase checks remain passing.
- Acceptance criteria: ✅ one successful summary per stored chat/week; ✅ all report fields, footer and button; ✅ complete help and rate-friendly existing editing; ❌ live Sunday group delivery not exercised without a token.
- Deviations from PLAN.md and why: "most active" was undefined. It is now explicitly defined in PLAN/README as distinct positive-scoring activity references in the existing ledger, not raw message counts. Mafia win/survival from one game count once. This avoids a new per-message counter or architecture change. Weekly ledger keys use the local Monday date. Delayed catch-up reports the stored due week; large outages do not replay every missed week. As with daily posts, ambiguous reserved/failed sends are not automatically replayed to prevent duplicates.
- Open questions / decisions needed: no blocking implementation question; Claude/owner can later decide whether raw message-volume activity is desired instead of scored participation.
- Known issues / TODO: local tests do not establish Telegram throughput. A crash/ambiguous delivery may leave a missing report rather than a duplicate. Real production content and live timezone/quiet-hour checks remain owner tasks.
- Manual test steps (Uzbek, simple):
  1. `alembic upgrade head` ni bajaring va botni ishga tushiring. Uch kishi vazifa/o‘yinlardan hafta davomida ball olsin.
  2. Yakshanba guruh vaqti 20:00–21:00 orasida bitta xulosa kelsin: top 5, eng faol, vazifa natijalari, shior, muallif va qo‘shish tugmasini tekshiring.
  3. Botni qayta yoqing: shu haftaning xulosasi takrorlanmasin. Tinch vaqt dushanbagacha bo‘lsa, kechikkan xulosa oldingi haftani saqlasin.
  4. Shaxsiy va guruh chatida `/help` yuboring: barcha mavjud buyruq va o‘yinlar ko‘rinsin, muallif va qo‘shish tugmasi ishlasin. LIVE_TEST 14-bo‘limini belgilang.


### Phase 9 — Result cards & deployment examples — 2026-11-07
- Status: implementation/local verification complete. Real Telegram and production deployment remain unverified.
- Commit(s): this entry accompanies `phase-9: licensed result cards and isolated deployment checks`; Phase 7 `32b6e73`, Phase 8 `3fb9dd2` are already pushed.
- What was built: deterministic 1000×820 Pillow PNGs for weekly top-five and completed game results, Instagram watermark, Unicode/control sanitizing and pixel-width name truncation; bundled unmodified Noto Sans with SIL OFL 1.1 license/source/hash. At most two off-event-loop renderers. Winner cards reserve once in existing game JSON through the shared locked repository; weekly cards use the existing scheduled-post ledger. GAME/BULK priorities preserved; normal final boards remain, weekly text is the fallback for render failure. `RESULT_CARDS_ENABLED` disables image work. Weekly captions retain every report field/button and fit Telegram's caption limit with shortened names.
- Files added/changed: card renderer/delivery service, game/weekly/runtime integration, locked game-card claims/audit, dare completion points, texts/config/.env.example, Noto font/license, Dockerfile/.dockerignore/Compose, systemd example, README deployment/backup/restore instructions, LIVE_TEST section 15, checker process-environment support, optional PostgreSQL integration test and card/checker tests. Backups/dumps ignored by Git and Docker. No new dependency or schema migration: Pillow was already planned, card audit uses existing JSON.
- Tests: full Windows suite with real PostgreSQL: **311 passed**; full Linux Docker suite with a fresh PostgreSQL database: **311 passed**; `ruff check .`: **all checks passed** on Windows and in Docker. Targeted card/checker tests: **49 passed**. Actual isolated PostgreSQL **16.14** smoke test: passed; Alembic upgrade/check, Unicode/UTC, buffered bulk upserts preserving opt-in, point idempotency, task completion, partial unique game constraint, atomic game points/card reservation, weekly reporting and indexed due scheduling with a ten-connection no-overflow pool. README's 12 PowerShell blocks parse without errors; Compose config validates with temporary fake environment values. Image `oqibat-review:phase9-55fcb39f` runs Python **3.12.16** as UID 10001, renders an Uzbek PNG with networking disabled, has no `/app/.env`, and passes `python -m bot --check` against the isolated PostgreSQL server with a read-only filesystem. Preview inspected visually outside the repo.
- Acceptance criteria: ✅ weekly/winner cards and watermark; ✅ bundled Uzbek-capable free font/license; ✅ actual PostgreSQL verification; ✅ Dockerfile + bot/PostgreSQL Compose + systemd example + step-by-step guide. Live image delivery/TLS/systemd/production restore and real 10,000-group capacity remain unverified. No deployment performed.
- Deviations from PLAN.md and why: game cards show this game's positive scores/winning side, maximum five rows; cancelled/refused/no-winner results have no winner image. Larger Mafia teams are truncated only visually, never in the point ledger. Cards add one GAME-priority upload after the final board; weekly uses one photo rather than photo plus duplicate text. A render failure preserves text, while an ambiguous upload is not automatically retried outside Sender's existing policy, preventing duplicate cards. Checker accepts complete environment configuration without a physical `.env`, required by secret-free container images. Docker uses PostgreSQL 16, verified locally, and Python 3.12. No architecture change.
- Build environment note: the ordinary Docker build reached dependency installation but PyPI transfers failed/stalled. Verification used a temporary copy of Dockerfile changing only pip's input to pre-fetched official PyPI Linux wheels, each checked against PyPI's SHA-256; dependency versions match the Windows suite. That install ran with `--network none`, followed by the same source/font/migration copies and non-root setup. The committed Dockerfile keeps normal PyPI installation with longer retries/timeouts. Its uninterrupted online-install path was not completed on this connection; the resulting offline-built runtime image and all tests passed. No third-party mirror package was used. Only uniquely named Oqibat review resources were created; other projects/containers/settings were not changed.
- Open questions / decisions needed: no implementation blocker. Owner/Claude should complete live testing and prepare real content before inviting users.
- Known issues / TODO: delivery reservations can remain reserved/failed after a crash; card uploads are not replayed on restart. All queued sends remain memory-only. A local PostgreSQL smoke test does not prove production throughput. Production deployment was deliberately not run; systemd/TLS/backup restore commands are examples, not verified server operations.
- Manual test steps (Uzbek, simple):
  1. `.env` da `RESULT_CARDS_ENABLED=true`, Instagram manzili to‘g‘ri bo‘lsin. Botni yoqing; ismida Oʻtkir/Gʻulom bo‘lgan a'zo bilan duelni yakunlang. Bitta rasm, to‘g‘ri ball va Instagram belgisi chiqsin.
  2. Viktorina, Krokodil, bajarilgan haqiqat/jasorat va Mafia g‘oliblarini tekshiring. Ballarni `/men` bilan solishtiring. Bekor o‘yinda g‘olib rasmi bo‘lmasin.
  3. Yakshanba xulosasi bitta top-5 rasm va to‘liq izoh/tugma bilan kelsin; qayta yoqilganda takrorlanmasin. Rasmni o‘chiruvchi sozlama bilan oddiy matnlar ishlasin.
  4. LIVE_TEST 15-bo‘limini bajaring. Server kerak bo‘lsa README dagi Docker yoki systemd yo‘lini faqat sinov botida tanlang; bir vaqtda bitta bot jarayoni ishlasin. Agent haqiqiy botni joylamadi.


### Final review summary — Phases 0–9 — 2026-11-07
- Status: implementation/local verification complete; stopped after the authorized Phase 9 finish. No Mini App, extra Mafia roles, seasons or achievements started. No real deployment or real Telegram messages sent.
- Commits pushed for this run: `32b6e73` Phase 7 Mafia; `3fb9dd2` Phase 8 weekly/help; `5f52453` Phase 9 result cards/deployment examples. This final documentation entry is committed/pushed separately.
- Done: foundation and scale services, consent/admin setup, daily posts/check-ins, challenges/penalties/points/stats, duels/quiz/polls, Krokodil, truth/dare, Mafia and requested safety rules/fuzz tests, weekly reporting/full help, licensed Uzbek result cards, environment checker, Uzbek live checklist, Docker/Compose/systemd examples and deployment/backup instructions. All six Claude review notes are checked above; the heap optimization remains a later measurement-triggered note as requested.
- Verification: **311 tests passed** on Windows with an isolated PostgreSQL server and **311 passed** in the Linux review container; Ruff passed on both. Alembic migration upgrade/schema checks passed on SQLite and PostgreSQL **16.14**. Offline startup/schema check and Uzbek PNG rendering passed in the non-root/read-only image. No `.env` was copied into that image. Default pytest without a local PostgreSQL URL has 310 passing cases and one intentionally skipped PostgreSQL test. Fake-clock limiter, scheduling offsets, independent deadlines, migration and 1,000-game Mafia invariants remain included. Details/online-build limitation are in Phase 9 above.
- Not verified: real BotFather getMe/username with owner credentials; real Telegram game/permission/DM/photo/429 flows and Sunday/quiet-hour delivery; public HTTPS webhook/reverse proxy; actual systemd service on a server; deployment, production backup/restore/upgrade/rollback; long-running operation or 10,000-group throughput. Docker Compose was configuration-validated, not started as a production stack. PostgreSQL was tested only in a dedicated temporary container/database, not an existing owner database. The image was built using verified prefetched official wheels after this connection's normal online installation stalled.
- Review artifact: ran `git archive --format=zip -o "..\oqibat-review-final.zip" HEAD`, verified the ZIP contains no `.env` and includes the font license. File: `D:\Coding projects\oqibat-review-final.zip`, outside the repo. It is refreshed after the final documentation commit so this summary is included; its ZIP comment records the final exact commit. The ZIP itself is not committed. The earlier `oqibat-review.zip` remains unchanged.
- Resource scope: only the uniquely named Oqibat review image and temporary test container/databases were used. The temporary PostgreSQL container is removed after the final tests; no production bot process was launched. Other projects, containers, volumes, Docker settings and existing databases were not changed. The review image `oqibat-review:phase9-55fcb39f` is retained locally.
- Top 5 risks before real users:
  1. **Live Telegram behavior:** mock-based acceptance cannot establish real DM blocking/role privacy, poll updates, admin rights, moderation, callback timing or photo/caption delivery. Finish LIVE_TEST with consenting testers; Mafia needs at least five people.
  2. **Capacity and queue growth:** 10,000 groups is a target, not measured production capacity. Global/chat limits and a single sending process can accumulate work. Monitor the five-minute metrics and profile Sender's heap if queue length exceeds 1,000 before expanding.
  3. **Crash/delivery gaps:** queued sends, buffered activity/check-ins and reservations are not a durable outbox. A crash can lose notifications or leave reserved/failed posts/cards undelivered; ambiguous sends are deliberately not blindly replayed. Mafia cancels on restart. Operate exactly one bot worker.
  4. **Production operations:** TLS, systemd hardening, database recovery/restore and upgrade/rollback remain unverified on the intended server. Test those with backups and a separate test bot/database; do not treat an isolated PostgreSQL smoke test as server acceptance.
  5. **Real content and group trust:** banks still contain three illustrative items each. Owner/Claude must provide appropriate varied Uzbek content and review consent, penalty choices and game rules before public groups; tiny banks repeat quickly.
- Manual handoff (Uzbek, simple):
  1. `D:\Coding projects\oqibat-review-final.zip` ni Claude ga ko‘rib chiqish uchun bering. `.env` yoki tokenni yubormang.
  2. README bo‘yicha sinov botini sozlang, migratsiya va `scripts/check_env.py` ni bajaring. Jonli sinovda `docs/LIVE_TEST.md` qadamlarini faqat haqiqatan o‘tganda belgilang.
  3. Avval uch kishilik guruhda oddiy imkoniyatlarni, keyin kamida besh kishi bilan Mafiani tekshiring. Xatoni vaqt va maxfiy qiymatlarsiz jurnal parchasi bilan yozing.
  4. Claude tekshiruvi va yuqoridagi ochiq sinovlar tugamaguncha haqiqiy foydalanuvchilarga ochmang. Bu ish shu yerda to‘xtaydi.


### Phase 10 — Preflight architecture gate (not implemented) — 2026-11-09
- Status: stopped before implementation under the owner's explicit instruction to stop if an architecture change is needed. This is not a completed Phase 10 or a completed Phases 10–14 run.
- Commit(s): this entry accompanies `docs: plan phases 10-14 and record durability architecture gate`.
- What was prepared: read AGENTS/PLAN/PROGRESS and checked all Claude notes (no unchecked implementation note). Added the owner's Phase 10–14 scope/acceptance criteria to PLAN before coding. Inspected the actual Sender callable/Future heap, 60-second activity/check-in buffers and reserve-before-send post flow. Wrote a concrete durability proposal and choices in `docs/PHASE10_ARCHITECTURE.md`. No runtime code, migrations, dependencies, commands or tests were changed.
- Blocker: top-five risk 3 is code-fixable only by changing the durability boundary. The existing sender stores non-replayable Python callables/Futures in memory; state commits and outbound effects are separate. Crash-safe business sends require serializable jobs committed with business state and recovery/ambiguity rules. Preserving ordinary-message zero SQL and 60-second bulk flush while also eliminating unflushed activity loss needs a persistent incoming journal/acknowledgement design. This is more than adding an index/retry or a routine new table, and was not silently authorized against the explicit stop condition.
- Tests: baseline `pytest -q`: **310 passed, 1 skipped** (optional local PostgreSQL test, no verification URL set); `ruff check .`: **all checks passed**. The first restricted Python launch failed with OS permission denied; rerun in the approved execution context passed. No new logic exists to test. No current PostgreSQL, Docker, server or Telegram checks are claimed for this preflight.
- Acceptance criteria: only planning/preflight done. `/stats`, `/maxfiylik`, confirmed self-deletion and Phase 10 risk fixes are NOT implemented. Phases 11–14 are NOT started. The existing `oqibat-review-final.zip` is unchanged; `oqibat-review-final2.zip` is not created because there is no completed new implementation to label final.
- Risk disposition (not fixes): risk 1 requires real Telegram acceptance; offline tests can expand coverage but cannot replace it. Risk 2 allows code profiling/heap optimization but still needs representative capacity testing. Risk 3 requires the architectural choice above. Risk 4 needs actual TLS/systemd/restore acceptance on the target environment. Risk 5 needs owner/Claude-authored content; Phase 14 tooling will validate it but must not invent production content. None is marked resolved by documentation.
- Deviations from PLAN.md and why: stopped at the explicitly allowed architecture gate before starting product implementation; added requested phase plans and a reviewable proposal rather than redesigning the delivery/storage contract. This run's sequential-phase authorization is recorded in PLAN.
- Open questions / decision needed: approve the scoped durable outbox and choose whether to retain or replace the bounded activity-loss window, OR explicitly authorize retaining the current memory-only contract and treating that risk as an architectural limitation for this run. See the proposal for boundaries, privacy implications and required tests. No real credential or server is required merely to make this decision.
- Known issues / TODO: all requested new features remain outstanding; no completed-phase claim, later-phase commits or final2 archive. Resume Phase 10 only once its architecture scope is decided.
- Manual review steps (Uzbek, simple):
  1. `docs/PHASE10_ARCHITECTURE.md` ni Claude bilan ko‘rib chiqing. Hozir yangi buyruq yoki imkoniyat qo‘shilmadi.
  2. Bot o‘chib qolsa yuborilmagan ishlarni bazadan tiklash kerakmi, oddiy xabar faolligining oxirgi 60 soniyasi yo‘qolishi qabul qilinadimi — shuni belgilang.
  3. Yangi saqlash tartibini tasdiqlang yoki shu safar mavjud cheklovni saqlab qolishga aniq ruxsat bering. Shundan keyin 10-bosqichdan davom etiladi; token yuborish kerak emas.


### Phase 10 — Hardening & owner tools — 2026-11-09
- Status: implementation/local verification complete. Claude explicitly approved the existing-row announcement approach; the preceding preflight gate is resolved and no general durable queue/journal was built.
- Commit(s): this entry accompanies `phase-10: bounded announcement recovery owner stats and privacy tools`.
- What was built: new announcement/skip/retry timestamps on challenges and claim/confirmation/retry timestamps on scheduled posts; indexed bounded startup/30-second tick recovery, six-hour age cutoff and ten-minute failure backoff, quiet-hour post deferral, original content/week identity, skipped old events. Missing/old never-announced assignments cancel without penalties. Resends only announce existing outcomes; all point writes remain in the state transaction, and moderation is never replayed. Historical pre-feature unconfirmed posts are aged out safely. A qualifying normal daily check-in flushes before update acknowledgement; ordinary activity remains SQL-free/buffered.
- Owner/privacy: private OWNER_ID-only `/stats` reports active groups, unique active opted-in users, unique users active in the last 24 hours, started games by type over seven days, queue length and tick time. `/maxfiylik` explains stored data in Uzbek; private `/malumotlarimni_ochir` uses a single-use requester-bound five-minute confirmation. Self-deletion coordinates chat locks and activity/check-in flush locks, removes personal rows/buffers/cached references, invalidates pending affected-chat effects, blocks stale messages/buttons/poll answers from recreating data, and permits deliberate re-entry via `/start`. Shared game records become anonymous cancelled tombstones with empty personal state and a shared non-person user ID 0; this prevents SQLite reusing game IDs referenced by other players' existing points. Already delivered Telegram messages/backups are explicitly excluded.
- Queue/shutdown: same one-process Sender/limiter, with a delayed readiness heap inside the same logical queue to avoid repeatedly rescanning chat-limited jobs. Accepted work survives caller cancellation until drain/close. Shutdown stops producers/new updates, flushes activity/check-ins, drains accepted sends for up to ten seconds, then cancels leftovers. No new dependency, external service or architecture redesign.
- Files added/changed: new migration `c106a5aa0010`, recovery and owner services, thin owner/privacy handlers, normal challenge/daily/weekly send integration, runtime/scheduler/sender lifecycle, privacy guards on game boards/cards/Mafia end messages, migration metadata merge, command registration/texts, README/PLAN/architecture-history notes and tests. Old committed migrations unchanged.
- Tests: `pytest -q`: **323 passed, 1 skipped** (optional PostgreSQL test, no test URL configured); `ruff check .`: **all checks passed**. SQLite `alembic upgrade head` and `alembic check`: passed, no model/schema drift. Thirteen new tests cover crash between committed outcome/send, fresh/repeated/stale recovery, no duplicate rows/points, no repeated moderation, retry backoff, owner/private boundaries, foreign confirmation, erasure/buffer and game-ID reuse, stale-update resurrection, and bounded graceful drain. Existing fake-clock limiter/priority, scale, game and migration suites pass. Group fixtures use the existing fake clock rather than real Telegram-rate waiting. Fake-token offline startup remains covered; no live Telegram claims.
- Top-five risk disposition: (1) live Telegram cannot be established by offline code; manual acceptance remains. (2) eliminated known repeated heap rescans, retained bounded queue/indexed work and exposed owner metrics; 10,000-group production capacity remains unproven. (3) implemented the approved bounded recovery/drain and accepted crash-loss contract in PLAN 10.11, without promising exactly-once messages. (4) actual TLS/systemd/server restore acceptance remains external, with existing examples/checker. (5) real content remains owner/Claude-authored; Phase 14 will add validation/guidance, not invent production banks.
- Acceptance criteria: owner/privacy/recovery and required source verification passed; real Telegram/private/group acceptance is unverified. No real bot credentials, deployment or server changes were used.
- Deviations and choices: preserve anonymous game IDs instead of deleting shared rows to protect other users' ledger references; erase associated personal JSON rather than retain names. Deletion guard is process-local and intentionally allows fresh data after `/start`; derived Telegram admin membership can be fetched again for permission checks. Old assignment notifications cancel safely instead of later penalizing an uninformed member. Ambiguous API acknowledgements can duplicate announcements within six hours, never awards. Recovery does not retry moderation. Default game restart behavior remains as previously implemented (Mafia cancels).
- Open questions: none blocking within Claude's approved direction. Live testing, production capacity and actual content remain unverified/external.
- Manual test steps (Uzbek, simple):
  1. Migratsiyani bajaring. Shaxsiy chatda `/maxfiylik` ni oching: saqlanadigan ma’lumotlar va o‘chirish chegarasi tushunarli bo‘lsin.
  2. `.env` dagi OWNER_ID egasi shaxsiy chatda `/stats` yuborsin. Guruh/a’zo/faollik/o‘yinlar va navbat ko‘rinsin; boshqa odamga ruxsat berilmasin, guruhda maxfiy statistika chiqmasin.
  3. Sinov a’zosi ball olib, o‘yinda qatnashsin. Shaxsiy chatda `/malumotlarimni_ochir` yuborib tasdiqlasin. Ballari/roziligi/ismli yozuvlari tozalansin, bog‘liq o‘yinlar tugasin; boshqalarning ballari saqlansin.
  4. Eski qo‘shilish tugmasi va xabarlar ma’lumotni qaytarmasin. `/start`, keyin yangi rozilik bilan boshlasa yangi ma’lumot yaratilsin; eski ballari qaytmasin.
  5. `pytest tests/test_hardening.py` bilan avariya/tiklashni tekshiring: olti soat ichida xabar tiklanadi, ball ikki marta yozilmaydi, eskisi yuborilmaydi. Ctrl+C da navbat ko‘pi bilan o‘n soniya kutilsin. Jonli tekshiruvda faqat sinov botidan foydalaning.


### Phase 11 — Seasons, streaks & achievements — 2026-11-09
- Status: implementation/local verification complete.
- Commit(s): this entry accompanies `phase-11: monthly seasons streak bonuses and achievements`; Phase 10 pushed as `1715674`.
- What was built: calendar-month UTC bounds derived from chat timezone; `/top` current season plus all-time without any ledger reset; indexed `next_season_at`, bounded scheduling, claimed-once previous-month champion cards (Pillow/text fallback), stable first-day 09:00–09:15 spreading, quiet hours and six-hour recovery. New migration `c111a5aa0011` initializes existing active/admin chats in 500-row keyset batches; runtime does not enumerate chats. Existing point-events `(chat_id, created_at)` index reused, not duplicated.
- Streaks/achievements: pure streak calculation; +3 at exactly day 7 and +10 at exactly day 30 of each consecutive local-date sequence. Bonus/base/unlock are in one transaction; duplicate inserts do not invoke milestones again. Bonus uses the base check-in reference so weekly activity is not inflated. Six per-chat/user code-defined achievements (first task/video, ten Krokodil guesses, first Mafia win, streak 7/30), `/yutuqlar`, on-demand historical reconciliation without retroactive points, and short claimed/batched BULK announcements. Added privacy deletion and supergroup migration/merge support for unlocks. Check-in flush resolves aliases and holds one chat lock at a time, protecting state/ledger from migration/erasure races.
- Files added/changed: achievements and season services, models/new migration, point/check-in integration, bounded scheduler/runtime/recovery integration, group stats command/texts, privacy and migration repositories, README/PLAN and tests. No new dependency; existing Pillow/font reused.
- Tests: `pytest -q`: **333 passed, 1 skipped** (optional local PostgreSQL test); `ruff check .`: **all checks passed**; fresh SQLite Alembic upgrade/check: passed, no drift. Targeted season/streak/achievement suite **10 passed**. Covers month/year/DST UTC boundaries, invalid naive time, sequence gaps/duplicates/month crossing, exact/repeated bonuses, rollback of base+bonus+unlock, task/video/Krokodil/Mafia milestones, batched priority/deduplication, real PNG season delivery once, retained ledger, monthly/all-time filtering and erasure. Updated explicit schema/table and migration fixtures for the new table.
- Acceptance criteria: offline implementation and targeted flows pass; live first-day Telegram delivery and multi-day user testing remain unverified. No real credentials/server needed for implementation.
- Deviations/choices: thresholds occur once per unbroken sequence (not every 7/30 days); season boundaries do not reset streaks. Only new qualifying check-ins earn bonuses; `/yutuqlar` may discover old achievements but never rewrites historical awards. Achievement announcements are low-priority claimed-before-send batches and may be lost, while permanent unlocks remain. Shared anonymous game tombstones from Phase 10 remain for ledger-reference safety; explicit user erasure is separate from monthly non-reset semantics. Long outages do not replay every missed month.
- Open questions / known limits: no blocker. Real Telegram/monthly scheduling, production PostgreSQL/load and owner-authored content remain external acceptance work. No claimed 10,000-group throughput.
- Manual test steps (Uzbek, simple):
  1. Migratsiyani bajaring. Guruhda `/top` yuboring: “Joriy mavsum” shu mahalliy oyning ballari, “Barcha vaqt” barcha ballarni ko‘rsatsin. Oy almashsa eski ballar o‘chmasin.
  2. `/yutuqlar` yuboring. Davra videosini bajaring: ilk vazifa va ilk video ochilsin. O‘nta Krokodil topishi yoki Mafia g‘alabasini tekshiring; xabarlar bitta qisqa to‘plamda kelsin.
  3. Har kuni kunlik xabardan keyin qatnashing. 7-kuni odatdagi +1 bilan yana +3, 30-kuni yana +10 bo‘lsin. Bir kun qoldirilsa seriya qayta boshlansin, oy almashishi esa uzmasin. Tez tekshiruv uchun `pytest tests/test_seasons_achievements.py` ishlating.
  4. Oyning 1-kuni 09:00–09:15 yoki tinch vaqt tugagach oldingi oy chempionlari rasmi kelsin. Qayta yoqilganda yana mukofot/ball yozilmasin; rasm o‘chirilgan sozlamada matn ishlasin.
  5. Tasdiqli o‘chirish yutuqlarni ham tozalasin; guruh superguruhga o‘tganda ular saqlansin.


### Phase 12 — Extended Mafia roles — 2026-11-09
- Status: implementation/local verification complete.
- Commit(s): this entry accompanies `phase-12: opt-in Don blocker and solo Mafia roles`; Phase 11 pushed as `34d7055`.
- What was built: new OFF-by-default per-chat `extended_roles` setting and migration `c112a5aa0012`; mode is snapshotted in the lobby and shown to players. Pure distributions add Don at 8+, town Ma'shuqa at 9+, solo Manyak at 11+, replacing existing roles without increasing mafia team size. Don participates in private mafia teammate lists/live tally, decides vote ties and reads non-mafia to the commissioner. Ma'shuqa blocks one actor, with consecutive-target prevention. Manyak selects a private night kill and wins alive with at most one other player. Town/mafia winner checks and scores/cards include all sides correctly.
- Night resolution: block first, simultaneous attackers, one doctor save covering both attacks; a killed doctor still saves and a blocked doctor has not successfully self-saved. Commissioner choices in blocker layouts resolve privately at dawn, including a blocked/no-result outcome; no immediate information leak through a callback. Multiple victims/roles are announced. New private buttons include session/round and existing stale/dead/context guards, per-chat locks, caps and GAME priority. Opt-out clears new role actions too. Default mode retains its original rules.
- Files added/changed: pure role/engine logic, Mafia service/keyboards/texts, settings/models/new migration, winner-card side handling, README/PLAN and new extended tests. No dependency/architecture change.
- Tests: full `pytest -q`: **353 passed, 1 skipped** (optional PostgreSQL); `ruff check .`: **all checks passed**; clean SQLite Alembic upgrade/check: passed, no drift. Original Mafia engine/flow suite **28 passed**; extended suite **20 passed**. Includes three complete scripted games (town, mafia, Manyak), all 5–15-player thresholds, tie/block interactions, simultaneous saves/deaths, doctor and repeated-block guards, commissioner/Don privacy, winner precedence, forfeits, setting snapshot/private callback/stale-round integration. Existing 1,000 base-mode random games plus 1,000 extended random games check valid distributions/outcomes, termination, no resurrection and rejected dead actions/votes.
- Acceptance criteria: all requested role behavior is implemented/tested offline; real 8/9/11-person play and private Telegram timing remain unverified. No deployment/real credentials used.
- Deviations/choices: Ma'shuqa is town; Don replaces one mafia, other new roles replace plain town. Setting changes affect the next lobby, not live roles. Simultaneous outcomes and Manyak precedence are specified in PLAN. A dead commissioner receives no new private result. These conservative game-rule details were documented before implementation; Claude may review balance, but they require no architecture redesign or implementation stop.
- Open questions / known limits: no blocker. Live balance/usability of the chosen extended layout, Telegram delivery pressure and real permissions still need consenting testers; local fuzzing is not a throughput benchmark.
- Manual test steps (Uzbek, simple):
  1. Migratsiyani bajaring. `/sozlamalar` dagi kengaytirilgan rollar dastlab o‘chiq bo‘lsin. Oddiy besh kishilik Mafia avvalgidek ishlasin.
  2. Rejimni yoqing. Kamida 8 kishi bilan Don chiqsin; mafia sheriklari uni shaxsiy chatda bilsin. Teng ovozda Don tanlovi hal qilsin, komissarga Don mafia emas bo‘lib ko‘rinsin.
  3. 9+ kishida Ma’shuqa bir harakatni to‘ssin. Bir xil odamni ketma-ket ikki kecha tanlay olmasin. Komissar tanlovi to‘silsa tongdagi shaxsiy doskada natija berilmasin.
  4. 11+ kishida Manyak yakka nishon tanlasin. Mafia bilan bir kechada ikki xil qurbon bo‘lishi mumkin; doktor saqlagan bitta nishon har ikkala hujumdan himoyalansin.
  5. Tinch/Mafia/Manyak g‘alabalarini tekshiring. Chiqqan odamlar va eski tur tugmalari ishlamasin. O‘yin paytida sozlamani almashtirish hozirgi rollarni o‘zgartirmasin.
  6. `pytest tests/test_mafia_engine.py tests/test_mafia_extended.py tests/test_mafia_flows.py` bilan ikkala ming o‘yinli tekshiruv va barcha ssenariylarni tez bajaring.


### Phase 13 — Telegram Mini App — 2026-11-09
- Status: implementation/local verification complete.
- Commit(s): this entry accompanies `phase-13: authenticated read-only Telegram Mini App`; Phase 12 pushed as `70502aa`.
- What was built: build-free Uzbek HTML/CSS/vanilla JS at `/webapp`, with Telegram themeParams/themeChanged handling, profile, season/all-time group rankings, own achievements and rules. User text uses DOM textContent, never HTML insertion. Optional HTTPS WEBAPP_URL adds private web_app buttons and group Main Mini App startapp URL buttons; blank keeps ordinary polling. Polling hosts aiohttp in the bot process; webhook mode shares its existing listener. Explicit static allowlist, no repository file serving, no-store/CSP headers and five concurrent, ten-second API requests.
- Security/data: every JSON route validates raw initData HMAC using the bot token and only its signed user ID, with constant-time comparison, duplicate-field/type checks, 24-hour expiry and 30-second future tolerance. Bot-token canonicalization excludes hash only (signature, if supplied, remains signed); this is distinct from third-party Ed25519 verification. No cookies/client-ID trust. Each group page checks live getChatMember with admin-capable bot and fails closed for departed users/unknown groups; startapp only selects a page. Global 429 pauses the shared Sender. Read-only projections expose no game JSON/roles and never create users, opt in, reconcile achievements or award points. Known-own-group and last-seen queries receive indexes in new migration `c113a5aa0013`.
- Files added/changed: auth/data/hosting services, thin HTTP handlers, static frontend, keyboards/private/group/runtime transport integration, config/.env.example/texts, migration/models, README domain/reverse-proxy/BotFather instructions and tests. No new dependencies or architecture change.
- Tests: full `pytest -q`: **380 passed, 1 skipped** (optional PostgreSQL URL unset in that run); `ruff check .`: **all checks passed**; `node --check bot/webapp/app.js`: passed. New suite **27 passed**, covering signature/signature-field tampering, wrong token, duplicate/malformed fields, identity types, exact expiry/future boundaries, all membership statuses, local HTTP auth/read-only/foreign-user and group access, departure after a prior successful request, unchanged DB counts, unknown user not created, static allowlist/headers, 429 pause, URL validation and private/group buttons/shared webhook routes. Frontend escaping/theme hooks are checked in delivered assets; actual browser/Telegram rendering is not claimed. One aiohttp advisory warns about string request-state keys; compatibility is retained with supported aiohttp 3.9+.
- Database/startup verification: fresh SQLite upgrade/check passed (no model drift); `python -m bot --check` passed using explicit fake credentials. An initial no-credential check correctly rejected absent settings, then the isolated fake-config check passed. Docker was available: separately ran the PostgreSQL integration test against a new empty, loopback-only PostgreSQL 16 Alpine container with tmpfs, **1 passed**, verifying migrations through Phase 13, schema drift, UTC, bulk upserts, ledger deduplication, game constraints, pool size and bounded due work. Only the uniquely named Oqibat test container was created/stopped/automatically removed; no other project resource changed.
- Acceptance criteria: requested source/auth/read-only routes/local tests implemented; actual own-domain HTTPS, BotFather configuration and Telegram mobile/desktop acceptance remain NOT verified. No deployment, real bot token or messages used.
- Deviations/choices: reuse existing HTTP bind host/port, strict /webapp URL path, live group membership rather than stale consent; profile's group picker is limited to 500 known active memberships, with group-link navigation for other groups. All runtime copy remains in texts.py. No blocker/open architecture question.
- Manual test steps (Uzbek, simple):
  1. Migratsiyani bajaring. Avval WEBAPP_URL bo‘shligida oddiy bot ishlashini tekshiring.
  2. README bo‘yicha o‘z domeningizda HTTPS va /webapp yo‘lini tayyorlang, WEBAPP_URL ni yozing, BotFather da asosiy Mini App ni yoqing. Bu sozlash hali avtomatik bajarilmagan.
  3. Shaxsiy /start → “Ilovani ochish”: o‘z profilingiz, ball va yutuqlar soni chiqsin. Guruh /help tugmasi o‘sha guruh reytingini ochsin.
  4. Mavsum/barcha vaqt, yutuqlar, qoidalar va Telegramning yorug‘/qorong‘i mavzusini tekshiring. Uzun yoki `<` belgili ism kodga aylanmay, oddiy matn bo‘lsin.
  5. Guruhdan chiqing, reytingni yangilang: ruxsat rad etilsin. Boshqa odamning ID sini havolaga yozish uning profilini ochmasin. Ilovani 24 soatdan keyin botdan qayta oching.
  6. Ilovani ochish ball yoki rozilikni o‘zgartirmasin. Xatoda vaqtni yozib, bot jurnalidagi “Mini App request failed” ni tekshiring; token/initData ni hech kimga yubormang.
