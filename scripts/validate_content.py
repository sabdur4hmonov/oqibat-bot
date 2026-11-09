"""Offline UTF-8 content validation: python scripts/validate_content.py."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot import texts  # noqa: E402
from bot.services.content_validation import validate_directory  # noqa: E402


def main(argv=None, emit=print):
    parser = argparse.ArgumentParser(description=texts.CONTENT_DESCRIPTION)
    parser.add_argument(
        "--directory", type=Path, default=ROOT / "data", help=texts.CONTENT_DIRECTORY
    )
    args = parser.parse_args(argv)
    report = validate_directory(args.directory)
    for name, count in report.counts.items():
        emit(texts.content_count(name, count))
    for issue in report.issues:
        emit(texts.content_issue(issue.file, issue.code, issue.item))
    emit(texts.CONTENT_BAD if report.issues else texts.CONTENT_OK)
    return 1 if report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
