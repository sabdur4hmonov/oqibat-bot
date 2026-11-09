# Content schema (version 1)

Each UTF-8 JSON file contains an array of objects. The committed files contain exactly
three examples each, not a production content bank. An empty array `[]` is valid;
future loaders must handle empty banks and any number of items without fixed-size assumptions.
The runtime content loader is Phase 2; no scheduled posts or games run in Phase 0.

Every item has a nonempty `key` string, unique across all banks, at most 128 characters.
Keep keys stable: `content_usage.content_key` and `challenges.prompt_key` reference them.
Text is plain Uzbek Latin, never trusted HTML. Future senders must HTML-escape it
and escape any substituted user/chat text. Only daily text supports `{group}`.

| File | Required fields in addition to `key` |
| --- | --- |
| `daily_messages.json` | `text`: nonempty string, optional `{group}` placeholder |
| `challenges.json` | `kind`: `video_note`, `voice`, `photo`, or `text`; `text`: nonempty prompt |
| `quiz_questions.json` | `question`: 1–300 chars; `options`: 2–10 distinct strings, 1–100 chars each; `correct_option_id`: zero-based index in options |
| `krokodil_words.json` | `word`: nonempty string, one word or phrase |
| `would_you_rather.json` | `question`: 1–300 chars; `options`: exactly two distinct strings, 1–100 chars each |
| `truth_questions.json` | `text`: nonempty question |

Adding production content does not require a database migration. Changing the schema
requires updating this document and the corresponding loader in the relevant phase.

Phase 14 authoring limits: daily/challenge/truth text at most 2,000 characters;
Krokodil word at most 100. The offline validator also rejects normalized duplicate
primary texts/options, unsupported/repeated placeholders, repeated JSON fields and
unknown/missing bank files. Daily text supports at most one `{group}`. Empty banks remain valid.
Run `python scripts/validate_content.py`; see the Uzbek [content guide](../docs/CONTENT_GUIDE.md).
