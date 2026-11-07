# Progress log

## Current status
- Current phase: Phase 0 foundation implemented; live Telegram verification pending. Stopped before Phase 1.
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
