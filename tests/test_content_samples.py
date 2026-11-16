import json

import pytest

from bot.services.content import FIELDS


@pytest.mark.parametrize("bank,fields", FIELDS.items())
def test_sample_bank_matches_documented_schema(content_directory, bank, fields):
    items = json.loads((content_directory / f"{bank}.json").read_text(encoding="utf-8"))
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


def test_content_keys_unique_across_banks(content_directory):
    keys = [
        item["key"]
        for bank in FIELDS
        for item in json.loads((content_directory / f"{bank}.json").read_text(encoding="utf-8"))
    ]
    assert len(set(keys)) == len(keys)
