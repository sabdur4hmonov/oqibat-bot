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

- Python 3.12, **aiogram 3.x** (long polling in dev; webhook optional in Phase 9)
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

### Phase 8 — Weekly summary & polish
Sunday 20:00 summary (top 5 of the week, most active, challenge stats, footer, add-to-group button),
`/help` per section 7, consistent emoji style in texts, rate-limit friendly editing everywhere.
**Accept:** summary posts once per week per chat.

### Phase 9 — Result cards & deployment
Pillow cards for weekly top and game winners (with `@INSTAGRAM_HANDLE` watermark, Uzbek-capable font
bundled in repo), PostgreSQL support verified, Dockerfile or systemd unit, deployment guide in README.

### Later (not now)
Telegram Mini App (leaderboards, Mafia voting screen), more Mafia roles, seasons and achievements.

## 9. Content

Codex creates only the loaders, schemas and 3 sample items per file. Real Uzbek content (daily messages,
challenges, quiz questions, Krokodil words, truth questions, would-you-rather pairs) is written by
Sardorbek and Claude and dropped into `data/` later. Code must handle 3 items or 3000.
