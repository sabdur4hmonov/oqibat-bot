import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from bot import texts
from bot.services.content import FIELDS, TEXT_LIMITS, validate_bank
from bot.services.content_validation import audit_bank, validate_directory
from scripts.validate_content import main

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def samples(kind):
    return json.loads((DATA / f"{kind}.json").read_text("utf-8"))


def banks(directory):
    for kind in FIELDS:
        (directory / f"{kind}.json").write_text("[]", encoding="utf-8")


def write(directory, kind, items):
    (directory / f"{kind}.json").write_text(json.dumps(items, ensure_ascii=False), "utf-8")


def test_every_committed_sample_valid_and_counted():
    report = validate_directory(DATA)
    assert report.issues == []
    assert report.counts == {f"{kind}.json": 3 for kind in FIELDS}


def test_empty_banks_valid_and_do_not_modify_files(tmp_path):
    banks(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert not validate_directory(tmp_path).issues
    assert all(count == 0 for count in validate_directory(tmp_path).counts.values())
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize("kind", FIELDS)
def test_primary_text_length_boundaries_in_shared_runtime_schema(kind):
    item = samples(kind)[0]
    field, limit = TEXT_LIMITS[kind]
    item[field] = "a" * limit
    assert not audit_bank(kind, [item])
    item[field] += "a"
    with pytest.raises(ValueError):
        validate_bank(kind, [item])
    assert audit_bank(kind, [item]) == [("schema", None)]


@pytest.mark.parametrize("kind", FIELDS)
def test_normalized_primary_duplicates_apostrophe_cyrillic_punctuation(kind):
    first = samples(kind)[0]
    primary = TEXT_LIMITS[kind][0]
    first[primary] = "O‘zbekiston"
    second = deepcopy(first)
    second["key"] += "_2"
    for variant in ["Oʻzbekiston", "Ўзбекистон", "  OZBEKISTON!!!  "]:
        second[primary] = variant
        assert audit_bank(kind, [first, second]) == [("duplicate_text", 2)]


@pytest.mark.parametrize("kind", ["quiz_questions", "would_you_rather"])
def test_normalized_option_duplicates_and_exact_limits(kind):
    item = samples(kind)[0]
    item["options"] = ["Oʻzbekiston", "Ўзбекистон"]
    assert audit_bank(kind, [item]) == [("duplicate_options", 1)]
    item["options"] = ["a" * 100, "b" * 100]
    assert not audit_bank(kind, [item])
    item["options"][0] += "a"
    assert audit_bank(kind, [item]) == [("schema", None)]
    item["options"] = [" ", "Ha"]
    assert audit_bank(kind, [item]) == [("duplicate_options", 1)]


@pytest.mark.parametrize("bad", [None, {}, [None], ["text"], [{"key": "wrong"}]])
def test_malformed_bank_shapes(bad):
    assert audit_bank("daily_messages", bad) == [("schema", None)]


@pytest.mark.parametrize(
    "change",
    [
        {"correct_option_id": True},
        {"correct_option_id": -1},
        {"correct_option_id": 10},
        {"correct_option_id": "1"},
        {"options": ["one"]},
        {"options": [str(i) for i in range(11)]},
        {"question": " "},
        {"extra": "not allowed"},
        {"key": ""},
        {"key": "k" * 129},
    ],
)
def test_quiz_schema_answer_options_fields_key_limits(change):
    item = samples("quiz_questions")[0] | change
    assert audit_bank("quiz_questions", [item]) == [("schema", None)]


def test_local_and_cross_bank_duplicate_keys(tmp_path):
    banks(tmp_path)
    first = samples("daily_messages")[0]
    write(tmp_path, "daily_messages", [first, first])
    assert any(issue.code == "schema" for issue in validate_directory(tmp_path).issues)
    write(tmp_path, "daily_messages", [first])
    second = samples("truth_questions")[0] | {"key": first["key"]}
    write(tmp_path, "truth_questions", [second])
    report = validate_directory(tmp_path)
    assert [(issue.file, issue.code, issue.item) for issue in report.issues] == [
        ("truth_questions.json", "duplicate_key", 1)
    ]


@pytest.mark.parametrize(
    "kind,text,valid",
    [
        ("daily_messages", "Salom, {group}!", True),
        ("daily_messages", "Salom!", True),
        ("daily_messages", "{group} {group}", False),
        ("daily_messages", "{name}", False),
        ("truth_questions", "{group}", False),
    ],
)
def test_placeholders(kind, text, valid):
    item = samples(kind)[0] | {"text": text}
    assert (not audit_bank(kind, [item])) is valid


def test_invalid_json_encoding_duplicate_object_fields_missing_unknown(tmp_path):
    banks(tmp_path)
    bad_files = {
        "daily_messages.json": b'[{"key":"one","key":"two","text":"hi"}]',
        "challenges.json": b"[broken",
        "quiz_questions.json": b"\xff",
        "krokodil_words.json": b"\xef\xbb\xbf[]",
        "unknown.json": b"[]",
    }
    for name, value in bad_files.items():
        (tmp_path / name).write_bytes(value)
    (tmp_path / "truth_questions.json").unlink()
    report = validate_directory(tmp_path)
    assert {(issue.file, issue.code) for issue in report.issues} == {
        ("daily_messages.json", "json"),
        ("challenges.json", "json"),
        ("quiz_questions.json", "json"),
        ("krokodil_words.json", "json"),
        ("truth_questions.json", "missing"),
        ("unknown.json", "unknown"),
    }


def test_cli_messages_counts_exit_and_no_env_or_network(tmp_path):
    banks(tmp_path)
    output = []
    assert main(["--directory", str(tmp_path)], output.append) == 0
    assert output[-1] == texts.CONTENT_OK
    assert len(output) == 7
    write(tmp_path, "daily_messages", {})
    assert main(["--directory", str(tmp_path)], output.append) == 1
    assert output[-1] == texts.CONTENT_BAD
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"BOT_TOKEN", "BOT_USERNAME", "DATABASE_URL", "OWNER_ID"}
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_content.py"), "--directory", str(tmp_path)],
        cwd=tmp_path,
        env=environment | {"PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 1
    assert "daily_messages.json: ? ta element" in result.stdout
    assert "schema" not in result.stdout and "Traceback" not in result.stderr
