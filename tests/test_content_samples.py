import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
BANKS = {
    "daily_messages": {"key", "text"},
    "challenges": {"key", "kind", "text"},
    "quiz_questions": {"key", "question", "options", "correct_option_id"},
    "krokodil_words": {"key", "word"},
    "would_you_rather": {"key", "question", "options"},
    "truth_questions": {"key", "text"},
}


@pytest.mark.parametrize("bank,fields", BANKS.items())
def test_sample_bank_matches_documented_schema(bank, fields):
    items = json.loads((DATA / f"{bank}.json").read_text(encoding="utf-8"))
    assert len(items) == 3
    for item in items:
        assert set(item) == fields
        assert 0 < len(item["key"]) <= 128
        for field in fields - {"options", "correct_option_id"}:
            assert isinstance(item[field], str) and item[field].strip()
        if "options" in fields:
            options = item["options"]
            assert 2 <= len(options) <= 10
            assert len(set(options)) == len(options)
            assert all(isinstance(option, str) and 0 < len(option) <= 100 for option in options)
            assert 0 < len(item["question"]) <= 300
        if bank == "quiz_questions":
            assert 0 <= item["correct_option_id"] < len(item["options"])
        if bank == "would_you_rather":
            assert len(item["options"]) == 2
        if bank == "challenges":
            assert item["kind"] in {"video_note", "voice", "photo", "text"}


def test_content_keys_unique_across_banks():
    keys = [
        item["key"]
        for bank in BANKS
        for item in json.loads((DATA / f"{bank}.json").read_text(encoding="utf-8"))
    ]
    assert len(set(keys)) == len(keys)
