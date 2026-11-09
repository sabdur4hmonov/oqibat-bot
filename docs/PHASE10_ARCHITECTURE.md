# Phase 10 durability decision — 2026-11-09

Status: historical proposal, superseded by the approved Claude decision on 2026-11-09.
Do NOT implement the general outbox/journal below. PLAN section 10.11 now authorizes
existing-row announcement flags, a six-hour recovery window and a ten-second drain.
The architecture gate is resolved. The original proposal is retained only as history.

The owner explicitly asked to stop if an architecture change is needed. Phase 10's
instruction to fix code-fixable top-five risks reaches the final summary's risk 3:
crash/delivery gaps. Eliminating those gaps changes existing guarantees in PLAN 10.5
and 10.10 and needs an explicit design decision. New tables alone are not the issue;
the boundary between accepting work, committing state and sending Telegram calls changes.

## Evidence in the current implementation

- `bot/services/sender.py`: `_Item.operation` is a Python callable with an asyncio Future.
  The heap and in-flight tasks exist only in memory. Callables/Futures cannot be replayed
  as stored Telegram jobs after process death.
- `bot/services/activity.py`: incoming activity/name changes accumulate in dictionaries;
  `run()` flushes every 60 seconds. Exception recovery restores memory, not a dead process.
- `bot/services/points.py`: `CheckinBuffer.pending` is also memory-only until bulk flush.
- `bot/services/daily.py` and `weekly.py`: commit a reserved post before awaiting a send.
  A crash before the API call leaves a reservation without a delivered message; blindly
  replaying a reservation can duplicate a send whose response was lost.
- Result cards use the same reserved-before-upload policy in game JSON. Game transitions
  dispatch process-local effects after the durable state transition.

More retries, shorter flush intervals or a clean-shutdown handler do not eliminate these
crash windows. Real Telegram/server testing remains external work and is not a reason
to block the other offline features by itself.

## Proposed architecture for reviewer approval

Keep one bot process, existing SQLAlchemy/Alembic stack and one rate-limited Sender.
Do not introduce Redis, another worker or a new Python dependency.

1. Introduce a database outbox for durable business notifications. Store a typed job,
   destination, payload/reference, priority, deduplication key, availability/deadline,
   attempts and delivery status, not pickled callables or private-role text in logs.
   Reserve the outbox job in the same transaction as its associated business outcome.
2. A bounded indexed dispatcher feeds eligible jobs to the existing global/chat limiter.
   Callbacks still bypass it; game deadlines never wait for delivery. Expired/stale game
   messages must be superseded or discarded rather than replayed into a later round.
3. Persist known success and safe failure outcomes. Mark ambiguous in-flight sends for
   reconciliation/operator visibility. Telegram sendMessage/sendPhoto provide no supplied
   application deduplication key in this implementation; do not promise exactly-once sends.
   Review polls, dice and moderation separately: replay can create a second random outcome
   or repeat a destructive action.
4. Decide the incoming-activity durability boundary separately. Retaining the mandatory
   no-DB-I/O ordinary-message path and 60-second bulk flush leaves a bounded crash-loss
   window. Eliminating it needs a persistent incoming journal/acknowledgement policy,
   with async I/O, recovery, retention and a writable persistent container volume. Do not
   silently add per-message SQL or weaken the scale requirement.
5. Self-deletion must purge/cancel pending durable jobs/journal entries and memory state,
   prevent in-flight flush resurrection and scrub user references in saved game JSON.
   Define how operator-managed backups and already-delivered Telegram messages are handled.
6. Add new migrations (never edit old ones), migration/recovery tests, crash injection at
   transaction/send/ack boundaries, privacy races, stale-effect tests and limiter tests.
   Update container/systemd persistence and backup instructions if a journal is selected.

## Decision needed

Choose either:

- Approve this scoped durability redesign, with a documented ambiguity policy, and decide
  whether ordinary activity may retain its current up-to-60-second crash-loss window.
  Full durable activity requires the additional persistent journal design above.
- Explicitly retain the existing memory-only delivery/activity contract for this run,
  accept risk 3 as an architectural limitation, and authorize Phase 10's remaining
  hardening/owner/privacy features followed by Phases 11–14.

Neither choice is assumed. Until resolved, Phase 10 is not implemented and Phases 11–14
are not started. The plan additions record requested scope, not acceptance or completion.
