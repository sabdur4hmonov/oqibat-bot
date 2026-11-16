# Content schema (version 1)

Each UTF-8 JSON file contains an array of objects. The nine committed banks now
contain owner-supplied production content from `oqibat-content.zip`, imported
unchanged in Phase 27. Their sizes can change; there is no fixed item count.
An empty array `[]` is valid and is handled safely by the runtime loader.
Small test banks live separately in `tests/fixtures/content/` and are copied to
temporary directories for tests; they are not used by the running bot.

Every item has a nonempty `key` string, unique across all banks, at most 128 characters.
Keep keys stable: `content_usage.content_key` and `challenges.prompt_key` reference them.
Text is plain Uzbek Latin, never trusted HTML. Senders must HTML-escape it
and escape any substituted user/chat text. Only daily text supports `{group}`.

| File | Required fields in addition to `key` |
| --- | --- |
| `daily_messages.json` | `text`: nonempty string, optional `{group}` placeholder |
| `challenges.json` | `kind`: `video_note`, `voice`, `photo`, or `text`; `text`: nonempty prompt |
| `quiz_questions.json` | `question`: 1–300 chars; `options`: 2–10 distinct strings, 1–100 chars each; `correct_option_id`: zero-based index in options |
| `krokodil_words.json` | `word`: nonempty string, one word or phrase |
| `would_you_rather.json` | `question`: 1–300 chars; `options`: exactly two distinct strings, 1–100 chars each |
| `truth_questions.json` | `text`: nonempty question |
| `secret_words.json` | `word`: one alphabetic token after normalization, at most 32 chars; a game needs at least players + 1 distinct words |
| `kim_aytdi_questions.json` | `text`: nonempty question, at most 300 chars |
| `telephone_phrases.json` | `text`: nonempty phrase, at most 300 chars |

Adding production content does not require a database migration. Changing the schema
requires updating this document and the corresponding loader in the relevant phase.

Phase 14 authoring limits: daily/challenge/truth text at most 2,000 characters;
Krokodil word at most 100. The offline validator also rejects normalized duplicate
primary texts/options, unsupported/repeated placeholders, repeated JSON fields and
unknown/missing bank files. Daily text supports at most one `{group}`. Empty banks remain valid.
Run `python scripts/validate_content.py`; see the Uzbek [content guide](../docs/CONTENT_GUIDE.md).
