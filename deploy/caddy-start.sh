#!/bin/sh
set -eu
: "${DOMAIN:?DOMAIN required}"
case "$DOMAIN" in
    *[!A-Za-z0-9.-]*|.*|*.) printf '%s\n' 'caddy_status=invalid_domain' >&2; exit 2 ;;
esac
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
