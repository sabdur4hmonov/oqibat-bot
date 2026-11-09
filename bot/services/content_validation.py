"""Offline content audit: runtime schemas plus authoring consistency checks."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bot.services.content import FIELDS, TEXT_LIMITS, validate_bank
from bot.utils.text_normalize import normalize_text


@dataclass(frozen=True)
class Issue:
    file: str
    code: str
    item: int | None = None


@dataclass
class Report:
    counts: dict[str, int | None]
    issues: list[Issue]


def audit_bank(kind: str, items) -> list[tuple[str, int | None]]:
    """Return stable error codes, never display untrusted JSON/exception strings."""
    try:
        validate_bank(kind, items)
    except (ValueError, TypeError):
        return [("schema", None)]
    issues = []
    seen = set()
    primary = TEXT_LIMITS[kind][0]
    for index, item in enumerate(items, start=1):
        text = normalize_text(item[primary])
        if text in seen:
            issues.append(("duplicate_text", index))
        seen.add(text)
        placeholders = re.findall(r"\{[^{}]*\}", item[primary])
        if placeholders and (kind != "daily_messages" or placeholders != ["{group}"]):
            issues.append(("placeholder", index))
        if "options" in item:
            options = [normalize_text(option) for option in item["options"]]
            if len(set(options)) != len(options) or any(
                not option.strip() for option in item["options"]
            ):
                issues.append(("duplicate_options", index))
    return issues


def unique_fields(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Repeated JSON field")
        values[key] = value
    return values


def validate_directory(directory: Path) -> Report:
    counts, issues = {}, []
    keys = set()
    try:
        files = {path.name: path for path in directory.glob("*.json")}
    except OSError:
        return Report({}, [Issue(directory.name, "unreadable")])
    expected = {f"{kind}.json" for kind in FIELDS}
    for name in sorted(expected | files.keys()):
        path = files.get(name)
        counts[name] = None
        if path is None:
            issues.append(Issue(name, "missing"))
            continue
        try:
            items = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_fields)
        except (ValueError, UnicodeError, RecursionError):
            issues.append(Issue(name, "json"))
            continue
        except OSError:
            issues.append(Issue(name, "unreadable"))
            continue
        if isinstance(items, list):
            counts[name] = len(items)
        if name not in expected:
            issues.append(Issue(name, "unknown"))
            continue
        kind = path.stem
        errors = audit_bank(kind, items)
        issues.extend(Issue(name, code, index) for code, index in errors)
        if any(code == "schema" for code, _ in errors):
            continue
        for index, item in enumerate(items, start=1):
            if item["key"] in keys:
                issues.append(Issue(name, "duplicate_key", index))
            keys.add(item["key"])
    return Report(counts, issues)
