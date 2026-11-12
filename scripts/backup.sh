#!/bin/sh
# PostgreSQL 16 client container; no binary stdout piping through PowerShell.
set -eu
umask 077
: "${PGHOST:?PGHOST required}"
: "${PGDATABASE:?PGDATABASE required}"
: "${PGUSER:?PGUSER required}"
BACKUP_DIR=${BACKUP_DIR:-/backups}
case "$BACKUP_DIR" in /|.|'') printf '%s\n' 'backup_status=invalid_directory' >&2; exit 2 ;; esac
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
temporary=$(mktemp "$BACKUP_DIR/.oqibat-$stamp-XXXXXX")
cleanup() { rm -f -- "$temporary"; }
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
pg_dump --format=custom --no-owner --no-acl --file="$temporary"
pg_restore --list "$temporary" >/dev/null
name=${temporary##*/}
destination="$BACKUP_DIR/${name#.}.dump"
test ! -e "$destination"
mv -- "$temporary" "$destination"
# Only completed Oqibat dump files in this dedicated directory. Prune after
# success so a failed dump never removes the last good recovery point.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'oqibat-*.dump' -mtime +13 -delete
find "$BACKUP_DIR" -maxdepth 1 -type f -name '.oqibat-*' -mtime +13 -delete
printf 'backup_status=ok backup_file=%s\n' "${destination##*/}"
