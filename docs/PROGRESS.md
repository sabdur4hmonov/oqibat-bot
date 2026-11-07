# Progress log

## Current status
- Current phase: Phase 5 implemented and locally verified; proceeding to Phase 6 under the owner's explicit request to continue through remaining PLAN phases.
- Last updated: 2026-11-07 (Asia/Tashkent)

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
