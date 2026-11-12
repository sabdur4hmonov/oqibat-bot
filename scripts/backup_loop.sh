#!/bin/sh
set -eu
while :; do
    if ! sh /scripts/backup.sh; then
        printf '%s\n' 'backup_status=failed next_attempt_seconds=86400' >&2
    fi
    sleep 86400 &
    wait "$!"
done
