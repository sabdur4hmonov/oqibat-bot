# Oqibat Bot — Product & Technical Plan

## 1. Product

**Name:** Oqibat (final bot username set via `.env`, e.g. `@OqibatBot`).
**Mission:** keep Telegram groups — classmates, friends, family, colleagues — alive and in touch.
Slogan (use in /start, /help, weekly summary): *"Guruhda oqibat bo‘lsin"*.
**Audience:** Uzbekistan. All user-facing text in **Uzbek Latin**. Default timezone `Asia/Tashkent`.

How it works: a group admin adds the bot as **admin**. Members opt in with one button. The bot then
posts daily messages, gives random members fun challenges (round video, voice, photo), keeps a shared
points economy with leaderboards, and runs group games (quiz, dice duel, Krokodil, truth-or-dare, Mafia).

**Growth (important for the owner):**
- Small footer `Muallif: @<INSTAGRAM_HANDLE>` only in /start, /help and the weekly summary (never on
  every message — no spam).
- A "Botni guruhingizga qo‘shing" button using the deep link
  `https://t.me/<BOT_USERNAME>?startgroup=add&admin=restrict_members+delete_messages+pin_messages`
  in /start, /help and weekly summary.

## 2. Telegram platform constraints (MANDATORY)

1. **No member list API.** A bot cannot list group members. The bot knows a user only if they:
   pressed the opt-in button, wrote a message, or joined while the bot was admin (`chat_member` update).
   Random picks are made **only among opted-in members**.
2. **The bot must be admin** to see all messages (needed to detect video notes/voice/photos) and to
   receive `chat_member` updates. On being added without admin rights, the bot posts a short message
   explaining how to make it admin and stays mostly idle until it is admin.
3. `allowed_updates` must include: `message`, `callback_query`, `my_chat_member`, `chat_member`,
   `poll_answer`.
4. **Restrict/kick** needs the `can_restrict_members` right. Admins and the owner can never be restricted —
   skip them silently. `until_date` must be between 30 seconds and 366 days from now.
5. **DMs:** the bot can only message users who pressed Start in a private chat. Sending to others raises
   `TelegramForbiddenError`. Flows that need DMs (Mafia) must use a URL button with a deep link
   `https://t.me/<BOT_USERNAME>?start=<payload>` so the user opens the bot first.
6. **Private info without DMs:** `answer_callback_query(text=..., show_alert=True)` shows a popup only to
   the user who pressed the button. Use this for Krokodil words and similar.
7. **Polls:** quiz polls must be `is_anonymous=False`, otherwise `poll_answer` updates never arrive.
   `open_period` max 600 s.
8. **Dice:** bot-sent dice (`send_dice`) are the only cheat-proof dice. If reading a user's dice message,
   reject forwarded ones (`message.forward_origin is not None`). Wait ~4 s after sending before
   announcing a result (animation). Verify value ranges per emoji in the Bot API docs.
9. **Limits:** roughly 20 messages/minute per group. Prefer **editing** one message (lobby, vote tally,
   scoreboard) over sending new ones. `callback_data` max 64 bytes — use short prefixes and ids.
10. **Bot commands** may contain only lowercase Latin letters, digits and `_`. Register them with
    `set_my_commands` separately for private chats and groups.

## 3. Tech stack

- Python 3.12, **aiogram 3.x** (long polling in dev; optional aiohttp webhook from Phase 0.5)
- **SQLAlchemy 2.x async** + **Alembic**; SQLite (`aiosqlite`) in dev, PostgreSQL (`asyncpg`) in prod,
  selected by `DATABASE_URL`
- **pydantic-settings** for config, `tzdata` for zoneinfo on Windows
- **Pillow** (Phase 9 result cards only)
- **pytest**, **pytest-asyncio**, **ruff**
- No APScheduler: use the scheduler "tick" described in section 6.1 (restart-safe, state in DB).

## 4. Project layout

```
oqibat-bot/
  AGENTS.md  README.md  requirements.txt  .env.example  .gitignore  alembic.ini
  alembic/
  data/                      # content banks (JSON, UTF-8)
    daily_messages.json  challenges.json  quiz_questions.json
    krokodil_words.json  would_you_rather.json  truth_questions.json
  docs/  PLAN.md  PROGRESS.md
  bot/
    __main__.py              # entrypoint: python -m bot
    config.py  texts.py
    db/        models.py  session.py  repo/ (one module per table group)
    handlers/  private.py  group_setup.py  settings.py  challenges.py  stats.py  games/
    services/  scheduler.py  points.py  picker.py  penalties.py  content.py  sender.py
    games/     dice_duel.py  quiz.py  wyr.py  krokodil.py  truth_dare.py  mafia/ (engine.py, roles.py)
    keyboards/
    utils/     text_normalize.py  time.py  admin.py
  tests/
```

## 5. Data model (initial)

- `chats`: id (tg chat id), title, is_active, bot_is_admin, tz (default Asia/Tashkent),
  daily_enabled, daily_time (HH:MM local), challenges_per_day (0–3, default 1),
  challenge_hours (2/6/10/24, default 10), penalty_mode (`off`|`points`|`mute`|`kick`, default `points`),
  mute_days (1/3/7, default 3), kick_after_misses (default 3), quiet_start (23:00), quiet_end (08:00),
  mafia_delete_dead_messages (bool, default false),
  created_at, updated_at
- `users`: id (tg user id), first_name, username, started_private (bool), created_at, updated_at
- `memberships`: chat_id, user_id, opted_in, opted_in_at, last_seen_at, last_picked_at,
  consecutive_misses, is_active
- `point_events`: id, chat_id, user_id, delta, reason (short code), ref_id (nullable), created_at
  → points are always computed as SUM over this ledger (never a mutable counter)
- `challenges`: id, chat_id, user_id, kind (`video_note`|`voice`|`photo`|`text`), prompt_key,
  status (`pending`|`done`|`missed`|`cancelled`), message_id, created_at, deadline_at, resolved_at
- `content_usage`: chat_id, content_key, used_at (avoid repeating content in a chat)
- `scheduled_posts`: chat_id, kind (`daily`|`weekly`), local_date — unique, so nothing posts twice
- `game_sessions`: id, chat_id, game (`quiz`|`duel`|`krokodil`|`hyj`|`mafia`), status
  (`lobby`|`running`|`finished`|`cancelled`), state (JSON), started_by, created_at, updated_at, phase_deadline_at
  → max one running session per chat (except duels, which may run alongside)

## 6. Core mechanics

### 6.1 Scheduler tick
A background task runs every 30 s. It does, idempotently:
- post daily messages for chats whose local time ≥ `daily_time` and no `scheduled_posts` row for today;
- assign challenges (spread over the non-quiet day window, `challenges_per_day` per chat, max one pending
  challenge per chat at a time);
- expire challenges whose `deadline_at` passed → mark missed, apply penalty;
- advance game phases whose `phase_deadline_at` passed (Krokodil rounds, Mafia phases, lobbies);
- post the weekly summary on Sunday 20:00 local.
Nothing is assigned during quiet hours. Deadlines that would end inside quiet hours are extended to
`quiet_end`. On startup, the tick also handles anything that became due while the bot was down.

### 6.2 Picker (random member)
Choose among opted-in, active members. Exclude anyone with a pending challenge and anyone picked in the
last 24 h if others are available. Weight by time since `last_picked_at` (longer wait = higher chance).
Pure function, unit-tested.

### 6.3 Challenge completion
A pending challenge is done when the picked user sends a message of the right kind in that chat before
the deadline (reply not required). Bot reacts with a short congratulation and awards points.
Other members cannot complete it for them.

### 6.4 Penalties (per chat setting, admins choose)
- `off`: nothing.
- `points` (default): points deducted + a funny "qarzdor" (debtor) mention in the next daily post.
- `mute`: points deducted + restrict for `mute_days` (send-messages off). Requires restrict right; skip admins.
- `kick`: only after `kick_after_misses` consecutive misses: ban then immediately unban (so they can rejoin
  via link), with a polite message. Requires restrict right; skip admins.
Any completed challenge resets `consecutive_misses`.

### 6.5 Points (constants in `services/points.py`)
| Event | Points |
|---|---|
| Daily check-in (first reply/message after the daily post, once per day) | +1 |
| Challenge done: video_note +15, voice +10, photo +10, text +5 | |
| Challenge missed | −5 |
| Quiz correct answer / first correct in question | +3 / +2 bonus |
| Dice duel win | +2 |
| Krokodil: guesser / host when guessed | +5 / +3 |
| Krokodil: host writes the word in chat | −3 |
| Truth answered / dare done (same as challenge kinds) / refused | +5 / by kind / −2 |
| Mafia: winning side / survived to the end | +10 / +3 |

### 6.6 Uzbek text normalization (`utils/text_normalize.py`)
Used for guessing games. Lowercase; unify all apostrophe variants (ʻ ʼ ’ ‘ ` ') to `'`; transliterate
Uzbek Cyrillic to Latin (ў→o', ғ→g', қ→q, ҳ→h, ш→sh, ч→ch, ё→yo, ю→yu, я→ya, etc.); strip punctuation
and extra spaces. "O‘zbekiston", "Oʻzbekiston", "O'zbekiston", "Ўзбекистон" and "Ozbekiston"
(apostrophe dropped) must all match the same word. Fully unit-tested.

## 7. Commands

Private: `/start`, `/help`.
Group: `/help`, `/qoshilish` (opt in), `/chiqish` (opt out, any time), `/men` (my points & stats),
`/top` (week + all-time), `/sozlamalar` (admins), `/vazifa` (admin: assign a challenge now),
`/viktorina`, `/duel`, `/krokodil`, `/hyj`, `/tanla`, `/mafia`, `/stop` (stop current game: admin or starter).

## 8. Phases

Each phase ends with the Definition of Done from AGENTS.md. Acceptance criteria are the minimum.

### Phase 0 — Foundation
Repo skeleton per section 4, requirements, `.env.example` (`BOT_TOKEN`, `BOT_USERNAME`, `DATABASE_URL`,
`INSTAGRAM_HANDLE`, `LOG_LEVEL`, `OWNER_ID`), `.gitignore`, config, DB models for section 5, first Alembic
migration, safe `sender.py`, global error handler, logging, `/start` and `/help` in private, command
registration, README with Windows setup/run steps, empty-but-valid data JSON files with 3 sample items each
and a documented schema.
**Accept:** `python -m bot` runs; /start answers in Uzbek with slogan, Instagram footer and add-to-group
button; `alembic upgrade head` creates the DB; tests for config and normalization skeleton pass.

### Phase 0.5 — Scale foundation
Implement section 10 before group features: a shared prioritized outbound queue, deterministic bulk
spreading, indexed due timestamps and bounded scheduler hooks, buffered activity and pending-challenge
lookup, admin cache, per-chat state locks, PostgreSQL pooling, optional authenticated aiohttp webhook,
load simulation and operational metrics. Keep later-phase product handlers unimplemented.
**Accept:** fake-clock global/chat limiter and spreading tests pass; migration/model consistency passes;
5,000-chat simulation processes at most 500 due rows per kind per tick and prints timings/counts;
normal group messages perform no database I/O; webhook authentication and lifecycle are tested locally.

### Phase 1 — Group onboarding & opt-in
`my_chat_member`: on add → welcome message with "O‘yinga qo‘shilish" button; detect admin rights and
explain how to grant them if missing; mark chat inactive when removed. Opt-in button, `/qoshilish`,
`/chiqish`, membership tracking (`last_seen_at` from any message), `chat_member` join/leave handling,
admin check helper, `/sozlamalar` inline menu editing every chat setting from section 5 (admins only,
non-admin presses get a popup).
**Accept:** add bot to a test group → welcome; press opt-in → registered; non-admin can't change settings;
removing/re-adding the bot works.

### Phase 2 — Scheduler & daily messages
Scheduler tick (6.1), content loader with no-repeat (`content_usage`), daily post with `{group}` placeholder,
daily check-in points, quiet hours.
**Accept:** with daily_time set 2 minutes ahead, exactly one post appears; restarting the bot does not
repost; check-in gives +1 once per day.

### Phase 3 — Challenges, points, penalties
Picker (6.2), challenge assignment message mentioning the user (HTML mention by id), completion detection
(6.3), expiry and all penalty modes (6.4), point ledger (6.5), `/vazifa`, `/men`, `/top`.
**Accept:** forced challenge → sending a round video completes it with +15; letting it expire applies the
chosen penalty; admins are never muted/kicked; unit tests for picker, deadlines/quiet hours, points.

### Phase 4 — Easy games
Dice duel (`/duel` as reply to someone or open challenge; emoji choice 🎲 🎯 🎳; bot rolls for both;
tie → reroll), quiz (`/viktorina`: 5 quiz polls, 30 s each, scores via `poll_answer`, final table by
editing one message), would-you-rather (`/tanla`: non-anonymous regular poll).
**Accept:** each game playable end-to-end in a test group; points recorded; `/stop` works.

### Phase 5 — Krokodil
`/krokodil`: host gets the word via `show_alert` popup ("So‘zni ko‘rish"), may skip twice per round;
others guess in chat; normalized matching (6.6); 3-minute rounds; correct guesser becomes next host;
timeout reveals the word and picks a random opted-in host; ends after 10 rounds or `/stop`; host
writing the word = −3 and new word.
**Accept:** full game with 3 people works; apostrophe/Cyrillic variants of the word are accepted.

### Phase 6 — Haqiqat yoki jasorat
`/hyj` (random opted-in member or reply target). Only the target can press "Haqiqat" / "Jasorat".
Truth: question, 30 min to answer (text or voice). Dare: reuses the challenge engine with a 1-hour
deadline. Refuse button → −2, no mute/kick.
**Accept:** both branches and refusal work; nobody else can press the target's buttons.

### Phase 7 — Mafia
Roles: mafia, doktor, komissar, tinch aholi. 5–6 players: 1 mafia; 7–9: 2; 10–15: 3. Always 1 doktor,
1 komissar. Lobby 90 s (`/mafia`), join via deep-link URL button (constraint 2.5), lobby message edited
with player list; cancel if fewer than 5. Roles sent by DM. Night 60 s: mafia choose a target by DM
buttons (majority, tie → random among tied), doktor saves one (not self twice in a row), komissar checks
one (learns mafia or not). Morning: announce victim (or "doktor saved"), reveal the victim's role.
Day: 90 s discussion, then 60 s vote with group inline buttons (only alive players vote, vote can be
changed, live tally by editing one message); most votes is eliminated, tie → nobody. Win: no mafia →
town wins; mafia ≥ others → mafia wins. Game state in `game_sessions.state`; on bot restart running
games are cancelled with an apology message. Engine logic pure and unit-tested (role distribution,
night resolution, vote resolution, win check).
**Accept:** a full 5-player game runs to a winner; dead players cannot vote or act; tests pass.

Owner additions for this run: join only through `start=mafia_<session_id>` while the lobby is open;
one active Mafia per user (including its lobby); prune forbidden role-DM recipients and recompute
roles before confirming play, continuing with 5+ remaining. Mafia members learn teammates and share
a private live tally; abstaining mafia cause no kill. All action callbacks include session + round,
reject stale/dead actors, and use GAME priority. Edit lobby/tallies. Optional dead-message deletion
defaults OFF and requires the bot's delete right. Draw after 20 rounds or 60 minutes. Stop/restart
cancels and privately notifies players. Test both winners and fuzz 1,000 complete games.

### Phase 8 — Weekly summary & polish
Sunday 20:00 summary (top 5 of the week, most active, challenge stats, footer, add-to-group button),
`/help` per section 7, consistent emoji style in texts, rate-limit friendly editing everywhere.
For the unspecified "most active" metric, use distinct positive-scoring activity references
from the weekly ledger (win + survival from one Mafia game count once), not raw message volume.
The report covers local Monday through delivery (or that week's end on delayed catch-up).
Quiet-hour deferral across Monday retains the original scheduled Sunday/week identity.
**Accept:** summary posts once per week per chat.

### Phase 9 — Result cards & deployment
Pillow cards for weekly top and game winners (with `@INSTAGRAM_HANDLE` watermark, Uzbek-capable font
bundled in repo), PostgreSQL support verified, Dockerfile or systemd unit, deployment guide in README.
Owner additions: bundle the free font's license; provide Dockerfile, bot + PostgreSQL Compose,
systemd example and step-by-step deployment instructions. Do not deploy. Verify PostgreSQL
locally if available, otherwise explicitly mark it unverified. Keep rendering off the event loop,
use the shared priority sender, and retain text results if rendering is unavailable.

### Phase 10 — Hardening & owner tools
Owner-authorized continuation: run Phases 10–14 sequentially, each with tests, pytest/Ruff,
PROGRESS entry, commit and push. Stop if an architecture change or real credentials/servers
are necessary, or tests cannot be made to pass. All existing scale rules remain mandatory.

Review every final-summary top-five risk: fix what code can fix and explain external limits.
Add private OWNER_ID-only `/stats`: active groups, distinct opted-in users, daily active
users, games by type over seven days, queue length and last tick duration. Define the
activity window explicitly. Add `/maxfiylik` in simple Uzbek and self-service deletion
`/malumotlarimni_ochir` behind a requester-bound confirmation button. Deletion must cover
durable records, JSON game references, pending buffers/caches and queued effects so stale
work cannot restore deleted data; explain that later new interaction can create new data.
Do not claim Telegram messages or external backups were deleted.
**Accept:** owner/private authorization and confirmation isolation tested; all advertised
metrics correct; deletion/races tested; each risk resolved or explicitly justified.
**Approved Claude decision (2026-11-09):** keep the in-memory Sender, no general durable
queue/journal. Follow section 10.11's bounded business-row announcement recovery and
10-second graceful drain. The previous architecture gate is resolved; routine choices
within this direction need no further stop. Never promise exactly-once Telegram delivery.

### Phase 11 — Seasons, streaks & achievements
Use calendar months in each chat's timezone. `/top` shows current season and all-time;
filter immutable `point_events` by UTC boundaries derived from the local month. Reuse the
existing `(chat_id, created_at)` index if it already satisfies the requirement; add a new
migration only for actual schema changes. Never reset the ledger. On the first day, publish
the previous season's champions with a Pillow card using indexed due work, stable spreading,
quiet hours and restart-safe deduplication. Daily check-in streak bonuses: 7 days +3,
30 days +10. Define threshold/repeat semantics explicitly before coding.
Define achievements in code (first round video, ten Krokodil guesses, first Mafia win,
seven-day streak and related milestones); `/yutuqlar` lists them. Batch short unlock
announcements at low priority. All awards/unlocks must be idempotent.
**Accept:** timezone/month/year boundaries, streak gaps, duplicate/concurrent awards,
batched announcements and restart-safe champion posting tested.

### Phase 12 — Extended Mafia roles
Chat setting `extended_roles` defaults OFF, introduced by a new migration. Preserve base
rules when OFF. Don at 8+ players: his vote breaks mafia ties; commissioner sees him as
town. Ma'shuqa at 9+: blocks one player's night action, never the same target twice in a
row. Manyak at 11+: solo night kill, wins alive with at most one other player. Town wins
only with no mafia and no manyak; mafia wins at parity only with manyak dead.
Before implementation, document role replacement/counts, Ma'shuqa alignment, night action
ordering, simultaneous kills/doctor saves and winner precedence; do not guess big decisions.
Extend scripted outcomes and 1,000-game fuzz invariants, private buttons/role descriptions,
stale/dead-action rejection and score/card handling. Preserve caps and GAME priority.
**Accept:** base mode unchanged; role thresholds, blocking, Don checks/ties, all winners,
termination and dead-player invariants tested in both modes.

### Phase 13 — Telegram Mini App
Serve build-free HTML/CSS/vanilla JS at `/webapp` through aiohttp in the same bot process;
adapt to Telegram themeParams. Configure HTTPS `WEBAPP_URL` in env; document the owner's
own domain and BotFather Main Mini App setup. Polling must still work; no deployment.
Pages: own profile, group season/all-time leaderboard, achievements and game rules.
Read-only JSON API validates Telegram initData HMAC with the bot token on every request,
rejecting data older than 24 hours. Verify group membership server-side before returning
any group data; a startapp chat ID is navigation input, never authorization.
Private chats use a web_app button; groups use a URL to the Main Mini App with
`startapp=<chat_id>`. All visible Uzbek copy remains centralized in `bot/texts.py`.
**Accept:** official-doc-verified signature algorithm, expiry/tampering/foreign-user/group
authorization tests, read-only routes, frontend escaping/theme handling and local aiohttp
lifecycle tests pass. Real HTTPS/Telegram-client acceptance is explicitly separate.

### Phase 14 — Content tooling
Add `scripts/validate_content.py` for all `data/*.json`: bank schemas, duplicate IDs/keys,
normalized duplicate text, length limits and per-file item counts; nonzero exit on errors.
Reuse existing normalization/schema rules. Add `docs/CONTENT_GUIDE.md` in Uzbek with
examples for every format. Real content remains owner/Claude-authored.
**Accept:** valid samples and empty banks handled according to existing schema; malformed
objects, duplicate identities/normalized text and length boundaries tested; PowerShell
instructions documented and all existing sample banks validated.

### Finish for Phases 10–14
After completing all phases, archive HEAD outside the repository as
`..\oqibat-review-final2.zip`, verify no `.env`, write a final honest PROGRESS summary,
commit/push and refresh the archive from that final commit, then stop. A blocked preflight
is not a completed phase and must never be represented as the final implementation archive.

### Later (not now)
Additional Mini App interactions beyond the read-only scope and further game features.

## 9. Content

Codex creates only the loaders, schemas and 3 sample items per file. Real Uzbek content (daily messages,
challenges, quiz questions, Krokodil words, truth questions, would-you-rather pairs) is written by
Sardorbek and Claude and dropped into `data/` later. Code must handle 3 items or 3000.

## 10. Scale

Target: 10,000+ groups on one server, with one bot process owning the in-memory queue/caches/locks.
All later phases must follow these rules; this section refines the scheduling times in section 6.

2. **Outbound limiter:** all sends/edits use the single async queue in `services/sender.py`.
   Enforce rolling limits of 25 attempts/second globally and 18 attempts/minute per chat, including
   retries. Priority: game interactions > challenges > daily/weekly posts. A paused chat must not
   block other ready chats. Retry once after `retry_after`, pausing the chat for a known chat limit
   or the whole queue for a global limit. Telegram supplies no scope flag: ambiguous limits default
   to a global pause; callers can explicitly identify a known chat limit. `answer_callback_query`
   uses the dedicated direct helper and is never queued or delayed by the message limiter.
3. **Spread bulk posts:** use a stable hash of `chat_id` (never Python's randomized `hash()`).
   Add 0–900 seconds to the configured local daily time. Spread Sunday summaries over local
   20:00–20:59:59 using a stable 0–3599 second offset. Recompute in the chat timezone, store UTC.
4. **Indexed due work:** chats have indexed UTC `next_daily_at`, `next_challenge_at`, `next_weekly_at`.
   Tick queries only `next_x_at <= now`, ordered by that timestamp, `LIMIT 500` per kind; process
   successfully and recompute the next time. Never read all chats to decide what is due. Add composite
   indexes `challenges(status, deadline_at)` and `game_sessions(status, phase_deadline_at)`, and apply
   the same bounded due-query rule to them. Onboarding/settings must initialize/recompute a chat's
   timestamps; disabled jobs use NULL. Unimplemented hooks leave due state untouched. Future post
   handlers must retain the `scheduled_posts` idempotency ledger and only advance on success.
5. **Incoming activity:** no per-message database writes or lookups. Coalesce `last_seen_at` and
   name/username changes in memory; flush every 60 seconds as one bulk operation (one upsert per
   affected table per bounded chunk, in one transaction; SQL cannot portably upsert two tables in
   one statement). Unknown groups must not be inserted by activity buffering. Load an in-memory set
   of `(chat_id, user_id)` for pending challenges at startup; all challenge status changes use the
   repository that synchronizes this set after commit. Normal message checks are set membership only.
6. **Admins:** cache each chat's admin IDs for 10 minutes, coalesce concurrent fetches, and invalidate
   and refresh on `chat_member` / `my_chat_member` updates. Failed refreshes must fail closed for
   permission/penalty decisions. No per-message admin API requests.
7. **State races:** all game/session writes use the shared per-chat `asyncio.Lock`, including creation,
   votes, callback actions and scheduler transitions. Use the game-session repository rather than
   direct writes. Do not hold a state lock while waiting for outbound messages. These locks are
   process-local; do not run multiple bot workers without redesigning coordination.
8. **Production transport/database:** production mode requires PostgreSQL, pool size 10–20 and no
   overflow. Polling remains the local default. Optional aiohttp webhook mode is configured with
   `USE_WEBHOOK`, HTTPS `WEBHOOK_URL`, `WEBHOOK_SECRET`, `WEBHOOK_HOST`, `WEBHOOK_PORT`; validate the
   secret header, preserve pending updates when switching transports, and document reverse-proxy TLS.
9. **Verification:** `scripts/simulate_load.py` creates 5,000 fake chats in an isolated test DB and
   runs actual scheduler ticks, printing tick duration and due items processed. Include fake-clock
   unit tests for both rate limits, priority/retry behavior and stable offset spreading. A local
   simulation is a foundation check, not proof of production capacity or Telegram delivery throughput.
10. **Metrics:** every five minutes log send queue length, updates in the last minute and last tick
    duration. Start/stop these tasks with the application, flush activity on clean shutdown, and
    cancel queued work safely. Monitor queue growth before increasing workload; memory buffers and
    queued sends are not durable across a crash.

11. **Approved crash contract/recovery:** losses of buffered last_seen/name updates,
    low-priority daily/weekly sends queued at crash time and running-game effects are
    accepted. Keep existing game restart cancellation/recovery policies; Mafia cancels.
    Do not build a general persistent queue or incoming journal. Important challenge
    assignment/result notifications use `assigned_announced_at` / `result_announced_at`
    on their existing rows. Posts are claimed before sending and `sent_at` is set only
    after Telegram confirmation. A bounded startup/tick pass retries unconfirmed events
    younger than six hours; older/inapplicable events are marked skipped. Use original
    dates/content and do not create another business row. An ambiguous lost API response
    can cause a duplicate announcement, but never duplicate points. Points commit in the
    state-change transaction, never in recovery/send code. Ordinary incoming activity
    stays buffered; scoring actions can persist their own award as existing games/tasks do.
    Stop accepting updates/new work on shutdown, flush activity/check-ins, allow accepted
    Sender work up to ten seconds to drain, then cancel the remainder and exit. Recovery
    never repeats moderation actions. Confirmed self-deletion removes live data and
    invalidates pending affected chat effects; already delivered Telegram messages and
    operator-managed backups are outside this command's deletion boundary.
