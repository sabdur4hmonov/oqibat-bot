# Oqibat Bot

**Guruhda oqibat bo‘lsin.** Telegram group engagement bot for Uzbekistan.
Python 3.12, aiogram 3, SQLAlchemy 2 async, Alembic. Phase 0 implements the foundation
and private `/start` and `/help`; group onboarding, schedules and games are later phases.

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

The example token is a placeholder. Do not commit `.env` or send the token in chat.
The username is checked against Telegram's `getMe` before polling. Secrets are
hidden in configuration representations/errors and redacted in runtime logs.

Create the database and start the bot, from the repository root:

```powershell
alembic upgrade head
python -m bot --check
python -m bot
```

`--check` validates configuration and checks that all initial tables exist; it does
not contact Telegram or authenticate the token. `python -m bot` registers commands
and runs long polling until Ctrl+C. Migrations read only `DATABASE_URL`, so they
work before Telegram credentials are set. Startup never creates tables implicitly.
Run `alembic upgrade head` after pulling schema changes. Never change a committed
migration; create a new revision for every later schema change.

The database URL can also be `postgresql+asyncpg://user:password@localhost/oqibat`.
The PostgreSQL driver and portable schema are included; live PostgreSQL verification
is scheduled for Phase 9. All stored timestamps are timezone-aware UTC at the ORM
boundary. SQLite values are reattached to UTC when loaded; naive input is rejected.
Chat-local clock settings default to Asia/Tashkent (daily 09:00, quiet 23:00–08:00).
Phase 0 does not run a scheduler or apply penalties.

## Telegram checks

1. Botning shaxsiy chatini oching va **Start** tugmasini bosing.
2. Salomlashuv, “Guruhda oqibat bo‘lsin”, Instagram manzili va guruhga qo‘shish
   tugmasi borligini tekshiring.
3. `/help` yuboring. Yordam va shu tugma chiqishi kerak.
4. “Botni guruhingizga qo‘shing” tugmasini bosing. Telegram guruh tanlash va
   administrator huquqlarini berish oynasini ochishi kerak.
5. Hozir guruhda o‘yin va qo‘shilish tugmalari yo‘q; ular keyingi bosqichda qo‘shiladi.
6. Botni to‘xtatish uchun PowerShell oynasida **Ctrl+C** bosing.

Only implemented private commands are registered. The group command scope is
explicitly registered as empty until group commands are implemented. Polling requests
`message`, `callback_query`, `my_chat_member`, `chat_member` and `poll_answer` updates;
group updates have no feature handlers yet. Private messages record reachability
without opting the user into any group. Every send uses `Sender`: a rate limit waits
and retries once; forbidden access clears `started_private` for a user or `is_active`
for a group; other failures are logged and return `None`. Cancellation still propagates.

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
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
