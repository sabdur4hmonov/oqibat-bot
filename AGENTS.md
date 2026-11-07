# AGENTS.md — rules for the coding agent (Codex)

You are the implementer on **Oqibat Bot**, a Telegram group-engagement bot for Uzbekistan.
The architect/reviewer is Claude; the owner is Sardorbek (beginner developer, Windows, PowerShell).
Claude designs and reviews, you write the code. The full spec is in `docs/PLAN.md`. Read it fully before any work.

## How you work

1. **One phase at a time.** Only do the phase you were asked to do (see `docs/PLAN.md` → "Phases").
   Never start the next phase on your own. When a phase is finished, stop and wait.
2. **Before coding a phase:** re-read that phase in `docs/PLAN.md` and the "Review notes from Claude"
   section of `docs/PROGRESS.md`. Apply every unresolved review note first.
3. **After finishing a phase:** fill in a new entry in `docs/PROGRESS.md` using the template there.
   Be honest: list what is NOT done, what you changed from the plan and why, and any open questions.
   Write the "Manual test steps" part in simple Uzbek (Latin) so Sardorbek can test in Telegram.
4. **Commit** with clear messages (`phase-1: group onboarding and opt-in`). Push to `origin main`
   if git credentials work; if not, say so in PROGRESS.md. Never force-push.
5. **Do not guess big decisions.** If the plan is unclear or wrong, pick the safest small option,
   write it under "Open questions" in PROGRESS.md, and continue. Do not redesign architecture.
6. **Do not invent Telegram features.** If unsure whether the Bot API or aiogram supports something,
   check the official docs (core.telegram.org/bots/api, docs.aiogram.dev). The constraints in
   PLAN.md section 2 are mandatory.

## Code rules

- Python 3.12, aiogram 3.x, async everywhere. Follow the stack and folder layout in PLAN.md exactly.
- **All user-facing text** lives in `bot/texts.py`, in Uzbek Latin. No user-facing strings in handlers.
  Use HTML parse mode and always `html.escape()` user names and any user-provided text.
- Keep handlers thin: Telegram I/O in `bot/handlers/`, logic in `bot/services/` and `bot/games/`.
  Game logic (roles, win checks, scoring, word matching) must be pure functions that are unit-testable
  without Telegram.
- All times are stored in UTC in the database; convert to the chat's timezone (default `Asia/Tashkent`)
  only for display and scheduling. `tzdata` must be in requirements (needed for zoneinfo on Windows).
- All Telegram sends go through one helper that catches `TelegramRetryAfter` (wait and retry once),
  `TelegramForbiddenError` (user blocked bot / bot kicked → mark inactive) and logs other errors.
  A single failing send must never crash a game loop or the scheduler.
- Any schema change = a new Alembic migration. Never edit an old migration.
- Secrets only in `.env` (never committed). Keep `.env.example` up to date.
- Add/update unit tests (`pytest`) for every piece of pure logic you write. Run `pytest` and
  `ruff check .` before every commit; both must pass.
- Commands must work in Windows PowerShell. Document run steps in `README.md`.
- No new dependencies beyond PLAN.md section 3 without writing the reason in PROGRESS.md.

## Definition of done for a phase

- Every acceptance criterion of the phase in PLAN.md is met (or explicitly listed as not met).
- `pytest` passes, `ruff check .` passes, bot starts with `python -m bot` without errors.
- PROGRESS.md entry written, committed, pushed (or push failure reported).
