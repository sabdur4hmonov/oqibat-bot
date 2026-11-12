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
| Yashirin target says secret word / correct expose / wrong expose | +10 (max 3) / +5 / −2 |
| Kim aytdi: correct guesser / unguessed author | +3 / +3 |
| Telephone: visible submitter after complete reveal | +3 |
| Eslaysizmi: correct guesser / sender if someone guessed | +3 / +2 |
| Admin hides a submitted item | no author bonus; compensate an already committed bonus once |

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
Implementation choices: milestones apply once at exactly day 7 and day 30 in each
unbroken daily-check-in sequence; a gap starts a new sequence, a calendar month does not.
Only newly committed qualifying check-ins earn bonuses (no retroactive ledger rewrite).
The existing daily date reference also identifies its bonus so activity is counted once.
Achievements are per chat/user and can reconcile past qualifying ledger history on
`/yutuqlar`; unlocks never themselves award extra points. Monthly champions post from
09:00 on the first, with stable 0–15-minute spreading and quiet-hour deferral. Migration
initializes existing chats in bounded batches; ticks query indexed due rows only.

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
Implementation choices: Don replaces one existing mafia (team size unchanged); Ma'shuqa
is a town blocker replacing a plain town role; Manyak replaces a plain town role. Roles
are snapshotted at lobby creation, so setting changes affect the next game. Resolve the
block first, then both killers simultaneously; the doctor's one saved target is protected
from either/both attacks, even if the doctor is killed that night. A blocked doctor has
not successfully self-saved. With a blocker in the role layout, commissioner checks are
selected immediately but revealed privately at dawn, so blocking cannot leak a result.
Don is mafia-aligned but reads non-mafia to the commissioner. Manyak's alive-with-at-most-
one-other win has precedence, then town elimination victory, then mafia parity with no
living Manyak. A night with zero survivors meets the town elimination condition. The
existing 20-round/60-minute draw remains the ultimate safety cap.

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
Implementation choices: blank WEBAPP_URL disables the optional HTTP Mini App in polling
mode. When enabled, polling starts the same-process aiohttp listener; webhook mode adds
the routes to its existing listener. Use the existing bind host/port. Every JSON API
request receives raw initData in `X-Telegram-Init-Data`, verifies HMAC/age (24 hours,
maximum 30 seconds future clock skew), and uses only the signed user ID. Verify current
group membership with getChatMember, not start_param or stale DB consent. No cookies,
tokens in URLs, API writes or Mafia-state/role endpoints. Bound API concurrency and
queries; HTTPS/public-domain and real Telegram client acceptance remain manual.

### Phase 14 — Content tooling
Add `scripts/validate_content.py` for all `data/*.json`: bank schemas, duplicate IDs/keys,
normalized duplicate text, length limits and per-file item counts; nonzero exit on errors.
Reuse existing normalization/schema rules. Add `docs/CONTENT_GUIDE.md` in Uzbek with
examples for every format. Real content remains owner/Claude-authored.
**Accept:** valid samples and empty banks handled according to existing schema; malformed
objects, duplicate identities/normalized text and length boundaries tested; PowerShell
instructions documented and all existing sample banks validated.
Implementation choices: reuse the runtime schema; cap daily/challenge/truth text at
2,000 characters (space for mentions/deadlines), quiz/WYR questions at 300, options
and Krokodil words at 100, keys at 128. Daily text may contain at most one {group};
other named brace placeholders are rejected. Keys are globally unique; normalized
primary text is unique within each bank and normalized options within each item.
The CLI rejects unknown/missing banks and repeated JSON object fields, reports all
files with counts, and runs without .env, Telegram or a database. Empty banks remain valid.

### Finish for Phases 10–14
After completing all phases, archive HEAD outside the repository as
`..\oqibat-review-final2.zip`, verify no `.env`, write a final honest PROGRESS summary,
commit/push and refresh the archive from that final commit, then stop. A blocked preflight
is not a completed phase and must never be represented as the final implementation archive.

### Phase 15 — Tosh–qaychi–qog‘oz (owner request, 2026-11-12)
Add `/tqq` (alias `/toshqaychiqogoz`) in groups. Two opted-in human members play
one simultaneous-choice round; reply to invite a specific member or use an open lobby.
Lobby expires after 90 seconds, accepted players have 60 seconds to choose. Each
player's first choice is final; reveal both only when both have chosen. Rock beats
scissors, scissors beats paper, paper beats rock. Winner +2 (same as dice duel),
draw/timeout/cancellation no points. No bot opponent or extra games in this phase.
Use the existing non-duel main-game slot, per-chat lock/repository, indexed independent
deadline loop, immutable point ledger and shared GAME-priority sender. Edit one board;
answer callbacks directly before effects. Include session ID + round in callbacks;
reject outsiders, bots, expired/foreign-board/stale/duplicate choices. Starter/admin
can /stop. Cancel without points on restart, group migration or a participant opting out/leaving.
Add pure winner/choice logic, thin handler, service, command/help/Mini App rules and
existing winner-card support. New Alembic revision adds `rps` to game type constraint;
keep all old migrations unchanged. SQLite parent-table rebuild must retain linked
challenge rows, run with foreign-key checks suspended only on the migration connection,
validate references before commit, and restore enforcement (per Alembic batch guidance).
**Accept:** all nine move pairs, hidden choices, join/target permissions, concurrent
duplicate taps, exact-once points, draw/timeout/stop/leave/restart, escaped names,
GAME priority, independent deadlines, migration of populated linked rows and existing
regression tests pass; pytest/Ruff, offline startup, PROGRESS entry, commit/push.
Real Telegram remains a separate manual acceptance check. No dependency or deployment.

### Phase 16 — Number hunt, quick maths and game discovery (owner request, 2026-11-12)
Owner authorized more games and polish; implement this bounded phase, then stop.
Add `/sontop`: secret integer 1–100, group members reply to the game board with a
number, narrowing higher/lower hints, 15 valid guesses maximum, 180 seconds from
confirmed board delivery, winner +3. One accepted guess per user per three seconds;
ignore malformed/out-of-range, forwarded, duplicate/older messages and guesses that
do not reply to the current board. Normal messages and rejected guesses do no SQL.
Add `/matematika`: five generated addition/subtraction/multiplication questions,
four inline choices each, 20 seconds per question from confirmed delivery. Distinct
correct values across the match; one attempt per opted-in user per round, max 500
distinct attempts/round. First correct earns +2 atomically with advancing state;
wrong answers get a private popup and no group edit. On timeout show the answer and
advance; end with a score table and optional existing result card, no extra final award.
Add `/oyinlar` in private/groups as a simple Uzbek catalog of all existing games.
Use the existing main slot, per-chat repository locks, GAME Sender priority, direct
callback replies, indexed independent deadlines and transactional point references.
Sending/preparing stages have a 90-second watchdog and accept no actions; only a
confirmed board starts the play window. Session/round/board checks reject stale math
buttons. Ended/cancelled games never accept actions. Restart/migration or starter
opt-out/leave cancels; committed earlier math awards remain. Other players can leave
without ending the match, and inactive players cannot earn new points. Preserve
privacy-erasure handling. No dictionary/content bank, dependency, deployment or
new persistent-queue design. New Alembic revision extends game CHECK to number/math;
old migrations unchanged, reuse Phase 15's validated SQLite parent rebuild handling.
**Accept:** pure generation/parser/answer/hint/limit/cooldown tests, complete scripted
games, concurrent winner/dedup/stale/foreign/permission tests, delivery-window/watchdog
and independent deadlines under send pause, normal-message zero SQL, stop/leave/
restart/migration/erasure, menu/help/card integration, linked-row migration safety,
pytest/Ruff/offline startup pass; write honest PROGRESS/manual Uzbek steps, commit/push.
Real Telegram and production capacity remain manual acceptance, not a deployment claim.

### Phase 17 — Production readiness (owner request)
Pin direct runtime dependencies to the exact installed/passing versions; separate
pytest/pytest-asyncio/ruff into requirements-dev.txt (including runtime requirements).
Docker installs runtime only. Add safe owner DMs for unhandled handler/scheduler and
background failures and repeated Sender errors (three failures within ten minutes).
Aggregate in memory, one alert per ten minutes including additional suppressed-error
count, type, fixed source identifier, chat ID and UTC time only. Never stringify
exceptions/messages or include credentials. Owner alert failures are non-recursive,
use the shared Sender, and cannot crash any worker. No durable queue/journal.
Add optional Compose `https` profile with DOMAIN-driven Caddy proxy/certificate
volumes, preserving webhook and Mini App paths/headers. Do not deploy or contact a
real domain. Document DNS A record, 80/443, URLs/secret and getWebhookInfo verification.
Automate daily custom-format pg_dump, retain completed Oqibat dumps for 14 days, add
scripts/backup.sh, validate before atomic rename and prune only after a successful
backup. Keep restore instructions consistent and demonstrate an isolated restore.
Add /healthz to webhook/Mini App HTTP applications: completed scheduler tick age and
send queue length, 503 until first successful tick or age >120 seconds. Production
polling also hosts health-only HTTP if Mini App is disabled, so Docker healthchecks
work; ordinary local development polling remains HTTP-free. Use stdlib Docker probe.
Replace aiohttp request-state strings with web.RequestKey; set .env.example
BOT_USERNAME=YourBotUsername (explicit placeholder, must be replaced with real username).
Rewrite LIVE_TEST.md as one Uzbek checklist for phases 0–16 with setup, three human
testers, expected results, log troubleshooting and no review ZIP step. Clearly mark
full Mafia/extended roles as requiring 5/8/9/11 real players; three people can test
minimum-player cancellation/settings and run offline suites, not certify full games.
**Accept:** pinned metadata/dev split, sanitized aggregation/rate/non-recursion,
handler/scheduler/Sender hooks, health freshness/status/hosting/probe, RequestKey,
Caddy/Compose validation and isolated backup/retention/failure/restore checks, complete
manual checklist, pytest/Ruff/offline startup pass. Write PROGRESS, commit/push, stop.
No schema change expected; no new Python dependency. Real DNS/TLS/Telegram and daily
wall-clock/live capacity checks remain explicitly unverified. No review archive.

### Phase 18 — Yashirin topshiriq and private-input foundation
Owner authorizes Phases 18–21 sequentially, each independently tested, logged, committed
and pushed. This overrides only the one-phase stopping rule. Reuse existing JSON game
sessions, repository locks, independent deadline loop and GAME-priority Sender.
Lobby joins are exclusively private /start deep links (<=64 characters). One active
private-input context per user across Mafia and all new games, including lobbies;
one shared join lock serializes cross-chat admission. Route private text/voice/photo
to that context, preserve normal commands. Release contexts on finish/cancel/erasure.
One background `secret` session per chat is independent of the main slot and duels.
All user submissions reject links/@mentions/forwards, enforce size/duration limits,
and escape HTML. User-content group posts have admin-only hide buttons bound to
session/item/message/chat. Hide atomically marks the item and reverses any author
award once through a compensating ledger event; never rewrite ledger history.
Try delete with the bot's delete right, otherwise replace text/caption with
"Admin tomonidan yashirildi". Telegram cannot replace a voice with text: media
games require delete permission before posting; if permission is later lost the
caption marks hidden but an admin must remove the media. Explain this limitation.
Keep bounded submissions/file IDs in session JSON, never download user media.
Add three samples each in secret_words.json (single word), kim_aytdi_questions.json
and telephone_phrases.json (text); runtime/offline validator and authoring guide agree.
Lobbies explicitly describe what will be published and require voluntary deep-link join.

`/yashirin`: five-minute lobby, 3–20 opted-in humans; starter chooses 2/6/24 hours
(default 24). Random single target cycle; unique active secret words from the bank.
Require at least players+1 distinct words to permit immediate replacement; samples
are illustrative, insufficient content cancels clearly rather than inventing words.
DM each hunter their target and word. New non-forwarded/non-edited target messages
(text/caption) match normalized whole tokens, or prefix for words >=4 letters.
Hunter +10, reveal word/group announcement, replace word, at most three successes.
`/fosh` replies to suspected hunter: a player accusing their actual hunter earns +5,
burns/reveals/replaces the word; wrong accusation costs 2 and one-hour cooldown.
At most three accusations/player/game. Serial state/points commits and message-ID
deduplication prevent duplicate scoring. In-memory per-chat word index rejects normal
messages without SQL. Leave/opt-out repairs the cycle (preserving remaining order),
cancels below three; starter leaving also repairs rather than ending a viable game.
Finished games edit a results table. Stop/restart/migration cancel and release private
contexts; confirmed erasure clears JSON/submissions and queued affected effects.
**Accept:** pure cycle/matching/repair tests; complete success/accusation/timeouts;
cross-game consent/context isolation, stale/foreign/bot callbacks, hide authorization
and award reversal, zero-SQL nonmatches, stop/restart/migration/erasure, no double
points; pytest/Ruff/offline startup; PROGRESS entry, commit/push before Phase 19.

### Phase 19 — Kim aytdi?
`/kimaytdi`, main slot, three-minute consent lobby, 4–12 opted-in humans joining
only through `start=kimaytdi_<session_id>`. Reuse Phase 18's global private context,
admission lock, submission validation, moderation, lifecycle and GAME Sender.
Everyone receives the same bank question privately, then has five minutes to send
one nonempty text answer (<=300 characters); reject voice/photo/links/@mentions,
forwards, edits and old messages. Start the input window after confirmed prompts;
90-second preparing/sending watchdogs cancel safely under delivery failure.
Shuffle submitted answers; non-submitters may still guess. If no answers, cancel.
Post each answer anonymously with player-name guess buttons and admin hide, wait
30 seconds from confirmed delivery, then reveal the author. Joined humans only,
one final guess/round, no self-answer vote; session/round/chat/message validation
rejects stale/foreign/bot callbacks. Correct guessers +3 each; author +3 if nobody
guessed, unless the item is hidden. State and all awards commit together with
unique session/item references. A later admin hide compensates author points once,
including after finish; never repost hidden text while revealing or retrying.
Use indexed deadlines and deferred sends; edit the original lobby into progress/
results and each answer into its reveal. Leave/opt-out cancels this main private
game, preserving earlier committed rounds. Stop/restart/migration/erasure cancel
and release contexts; erasure clears submissions, no late disclosure from queues.
New migration adds `kim` to the CHECK; preserve populated parent links and indexes.
**Accept:** complete scripted correct/nobody-guessed flows, text limits/escaping,
single-context consent, timeouts/empty answers, callbacks/permissions, admin hide
before/after award, concurrent/no-double points, all lifecycle paths, regression
pytest/Ruff/offline startup; PROGRESS, commit/push before Phase 20. Live play needs
four real participants; a three-person group can only verify minimum cancellation.

### Phase 20 — Ovozli buzilgan telefon
`/telefon`, main slot, three-minute consent lobby, 4–10 people. Deep-link-only
join `telefon_<session_id>` and shared one-private-context admission, media/input
validation, admin hide, sender and lifecycle rules from Phase 18 apply. Require
bot delete permission before starting and before posting group media; if permission
is lost later, caption marking is explicitly not physical media removal.
Shuffle the player order. First speaker receives a bank phrase privately as text;
each subsequent speaker receives only the previous valid voice re-sent by file_id,
with generic instructions, never the original phrase or previous person's identity.
Each turn has two minutes after confirmed prompt delivery. Speakers submit one new
voice <=30 seconds; the last player submits heard text (1–300 characters). No file
downloads, forwarded content, links/@mentions, wrong media, stale or duplicate input.
Accept prompt-delivery-race input for the current turn only. On timeout or failed DM,
skip and pass the last valid voice; before any voice exists the next non-last speaker
receives the original phrase. With no voice at the last turn, end without invented
audio; missing final text is identified plainly. Cancel if nobody submitted.
Reveal original phrase, final text (or missing-text notice), then voices in turn order.
Every user-text/voice post has its own author-bound admin hide. Keep group file IDs
and message IDs in bounded session JSON for moderation, not media bytes. Award each
non-hidden submitter +3 once, transactionally when the reveal completes; no points
on cancellation, and later hide compensates author points once. Keep confirmed
progress/reveal stages and 90-second watchdogs in game state; no new send journal.
All I/O uses GAME Sender; deadlines only transition/schedule effects. Shared stop,
restart, migration, erasure and withdrawal cancel/release contexts and suppress late
queued media. Extend CHECK with `telephone` in a new migration, old migrations unchanged.
**Accept:** full voice chain/final text, previous-voice-only privacy, shuffled order,
voice/text boundaries, timeout/DM-failure skips, no-response end, consent/context,
admin-only hide/no double points, stale/foreign/bot callbacks and all lifecycle paths;
populated migration, pytest/Ruff/offline startup; PROGRESS entry, commit/push before
Phase 21. Full live play requires four humans; no deployment or review ZIP.

### Phase 21 — Eslaysizmi? and final game discovery
`/eslaysizmi`, main slot, five-minute consent lobby, 3–10 opted-in people.
Deep-link join `eslaysizmi_<session_id>`, global private context (Mafia included),
bot delete permission, shared validation, admin hide and lifecycle rules apply.
Each person sends one new photo privately within five minutes, with an optional
caption (when/where, <=300 characters). Photos only; retain only the Telegram
file_id for media, plus the consented caption/author/phase/message metadata in
bounded existing session JSON; never download/store image bytes, sizes or URLs.
Reject forwards/edits, links/@mentions, wrong media, old/duplicate submissions.
Accept early replies during prompt delivery. Shuffle received photos; missing
submitters may still guess, play received photos after collection timeout, cancel
if none. Post one at a time via sendPhoto(has_spoiler=True); caption stays hidden
until the 30-second guessing period ends. Named buttons, one final vote per joined
human per round, no self-photo vote. Reveal sender/caption by editing that photo's
caption, not resending the image. Correct guesser +3; sender +2 if at least one
other player guessed, zero sender bonus if hidden. Transactional idempotent awards;
late hide compensates sender bonus once. Never restore hidden photos/captions.
Require current delete permission before posting media; caption fallback honestly
warns that the image still needs human removal if deletion fails or rights vanish.
Reuse independent indexed deadlines and 90-second send watchdogs; all sends GAME
priority. Stop/restart/migration/erasure/withdrawal cancel/release private context
and suppress pending disclosures. Preserve item origin to reject migrated message
ID reuse; privacy erasure clears file IDs and captions. New `memory` CHECK migration,
old migrations unchanged. Extend existing anonymous-guess engine rather than create
a different game architecture or a durable outbound journal.
**Accept:** full games with guessed/unguessed/hidden bonuses; actual photo/spoiler/
caption calls, safe stored shape, input limits, consent/context, stale/foreign/bot/
self callbacks, no double points, collection/lobby/send timeouts, all lifecycle and
privacy/migration paths; populated SQLite migration, final PostgreSQL head if local,
pytest/Ruff/offline startup. Update /oyinlar, /help, group commands, Mini App rules,
README and complete Uzbek LIVE_TEST checklist for Phases 0–21 (four people needed
for Kim/Telephone, extra Mafia participants as before). Write PROGRESS entry and
final honest summary, commit/push, stop. No Phase 22, deployment or review ZIP.

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
