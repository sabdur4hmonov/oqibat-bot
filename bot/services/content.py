"""Validated UTF-8 content banks, loaded once. Selection logic is pure."""

import json
import random
from pathlib import Path

FIELDS = {
    "daily_messages": {"key", "text"},
    "challenges": {"key", "kind", "text"},
    "quiz_questions": {"key", "question", "options", "correct_option_id"},
    "krokodil_words": {"key", "word"},
    "would_you_rather": {"key", "question", "options"},
    "truth_questions": {"key", "text"},
}


def validate_bank(kind: str, items) -> list[dict]:
    if not isinstance(items, list):
        raise ValueError("Content bank must be an array")
    keys = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != FIELDS[kind]:
            raise ValueError("Content object has incorrect fields")
        if (
            not isinstance(item["key"], str)
            or not 0 < len(item["key"]) <= 128
            or item["key"] in keys
        ):
            raise ValueError("Invalid or duplicate content key")
        keys.add(item["key"])
        for field in FIELDS[kind] - {"options", "correct_option_id"}:
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError("Content fields must be nonempty strings")
        if "options" in item:
            options = item["options"]
            if not isinstance(options, list) or not 2 <= len(options) <= 10:
                raise ValueError("Invalid options")
            if any(not isinstance(option, str) or not 0 < len(option) <= 100 for option in options):
                raise ValueError("Invalid option text")
            if len(set(options)) != len(options) or len(item["question"]) > 300:
                raise ValueError("Duplicate options or oversized question")
        if kind == "quiz_questions" and (
            type(item["correct_option_id"]) is not int
            or not 0 <= item["correct_option_id"] < len(item["options"])
        ):
            raise ValueError("Invalid correct answer index")
        if kind == "would_you_rather" and len(item["options"]) != 2:
            raise ValueError("Would-you-rather requires two choices")
        if kind == "challenges" and item["kind"] not in {"video_note", "voice", "photo", "text"}:
            raise ValueError("Invalid challenge kind")
    return items


def choose_content(items: list[dict], used: dict, rng=None) -> dict | None:
    if not items:
        return None
    rng = rng or random
    fresh = [item for item in items if item["key"] not in used]
    if fresh:
        return rng.choice(fresh)
    oldest = min(used[item["key"]] for item in items)
    return rng.choice([item for item in items if used[item["key"]] == oldest])


class ContentLibrary:
    def __init__(self, directory: Path | None = None) -> None:
        directory = directory or Path(__file__).resolve().parents[2] / "data"
        self.banks = {}
        keys = set()
        for kind in FIELDS:
            items = validate_bank(kind, json.loads((directory / f"{kind}.json").read_text("utf-8")))
            if keys.intersection(item["key"] for item in items):
                raise ValueError("Content keys must be unique across banks")
            keys.update(item["key"] for item in items)
            self.banks[kind] = items

    async def draw(self, sessions, chat_id: int, bank: str, now) -> dict | None:
        from sqlalchemy import select

        from bot.db.models import ContentUsage

        async with sessions.begin() as session:
            used = dict(
                (
                    await session.execute(
                        select(ContentUsage.content_key, ContentUsage.used_at).where(
                            ContentUsage.chat_id == chat_id
                        )
                    )
                ).all()
            )
            item = choose_content(self.banks[bank], used)
            if item is not None:
                await session.merge(
                    ContentUsage(chat_id=chat_id, content_key=item["key"], used_at=now)
                )
            return item
