"""Opt-in Windows-compatible shell tests in an isolated, networkless client image."""

import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(
    os.environ.get("OQIBAT_TEST_BACKUP_DOCKER") != "1",
    reason="Set OQIBAT_TEST_BACKUP_DOCKER=1 with cached postgres:16-alpine",
)
@pytest.mark.parametrize("failure", ["none", "dump", "restore"])
def test_atomic_backup_retention_failure_cleanup_and_no_unrelated_deletion(tmp_path, failure):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    backups = tmp_path / "backups"
    backups.mkdir()
    (binaries / "pg_dump").write_text(
        '#!/bin/sh\n[ "$FAILURE" != dump ] || exit 1\n'
        'for argument in "$@"; do\n'
        'case "$argument" in --file=*) output=${argument#--file=};; esac\ndone\n'
        'printf testdump > "$output"\n',
        encoding="utf-8",
        newline="\n",
    )
    (binaries / "pg_restore").write_text(
        '#!/bin/sh\n[ "$FAILURE" != restore ]\n', encoding="utf-8", newline="\n"
    )
    old = backups / "oqibat-old.dump"
    recent = backups / "oqibat-recent.dump"
    unrelated = backups / "other-project.dump"
    old_partial = backups / ".oqibat-stale-partial"
    recent_partial = backups / ".oqibat-recent-partial"
    for path, days in [
        (old, 15),
        (recent, 13),
        (unrelated, 20),
        (old_partial, 15),
        (recent_partial, 13),
    ]:
        path.write_bytes(b"retained")
        stamp = time.time() - days * 86400
        os.utime(path, (stamp, stamp))
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "/bin/sh",
            "--mount",
            f"type=bind,source={tmp_path},target=/case",
            "--mount",
            f"type=bind,source={ROOT / 'scripts/backup.sh'},target=/backup.sh,readonly",
            "-e",
            f"FAILURE={failure}",
            "-e",
            "PGHOST=test",
            "-e",
            "PGUSER=test",
            "-e",
            "PGDATABASE=test",
            "-e",
            "PGPASSWORD=do-not-print",
            "-e",
            "BACKUP_DIR=/case/backups",
            "postgres:16-alpine",
            "-ec",
            (
                "cp -R /case/bin /tmp/testbin\nchmod +x /tmp/testbin/*\n"
                "export PATH=/tmp/testbin:$PATH\nsh /backup.sh"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (result.returncode == 0) is (failure == "none"), result.stderr
    assert "do-not-print" not in result.stdout + result.stderr
    assert old.exists() is (failure != "none")
    assert recent.read_bytes() == unrelated.read_bytes() == b"retained"
    assert old_partial.exists() is (failure != "none")
    assert recent_partial.read_bytes() == b"retained"
    assert set(backups.glob(".oqibat-*")) == (
        {old_partial, recent_partial} if failure != "none" else {recent_partial}
    )
    new = [path for path in backups.glob("oqibat-*.dump") if path not in {old, recent}]
    assert len(new) == (1 if failure == "none" else 0)
    if new:
        assert new[0].read_bytes() == b"testdump"
