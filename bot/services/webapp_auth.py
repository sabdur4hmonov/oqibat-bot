"""Bot-token initData HMAC validation per core.telegram.org/bots/webapps.

The bot-token method excludes hash only; the Ed25519 third-party method is distinct.
Never authenticate using initDataUnsafe or a client-provided user/group identity.
"""

import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    user_id: int
    first_name: str
    username: str | None
    start_param: str | None


def validate_init_data(raw: str, token: str, *, now=None) -> Identity:
    if not isinstance(raw, str) or not raw or len(raw) > 8192:
        raise InitDataError("invalid")
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, errors="strict")
        fields = dict(pairs)
        if len(fields) != len(pairs) or not all(
            re.fullmatch(r"[A-Za-z0-9_]+", key) for key in fields
        ):
            raise ValueError()
        received = fields.pop("hash")
        if len(received) != 64:
            raise ValueError()
        received = bytes.fromhex(received)
        canonical = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret, canonical.encode(), hashlib.sha256).digest()
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise InitDataError("invalid") from None
    if not hmac.compare_digest(expected, received):
        raise InitDataError("invalid")
    try:
        value = fields["auth_date"]
        if not value.isascii() or not value.isdecimal():
            raise ValueError()
        issued = int(value)
        user = json.loads(fields["user"])
        if (
            not isinstance(user, dict)
            or type(user.get("id")) is not int
            or not 0 < user["id"] < 2**63
        ):
            raise ValueError()
        name, username = user.get("first_name", ""), user.get("username")
        if not isinstance(name, str) or (username is not None and not isinstance(username, str)):
            raise ValueError()
    except (ValueError, KeyError, TypeError, RecursionError):
        raise InitDataError("invalid") from None
    now = time.time() if now is None else now
    if issued > now + 30:
        raise InitDataError("invalid")
    if now - issued > 86400:
        raise InitDataError("expired")
    return Identity(user["id"], name[:255], username, fields.get("start_param"))
