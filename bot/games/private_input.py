"""Pure admission, submission and secret-mission rules."""

import random
import re

from bot.utils.text_normalize import normalize_text

PRIVATE_GAMES = {"mafia", "secret", "kim", "telephone", "memory"}
LOBBY_LIMITS = {
    "secret": (3, 20, 5),
    "kim": (4, 12, 3),
    "telephone": (4, 10, 3),
    "memory": (3, 10, 5),
}
PREFIXES = {
    "mafia": "mafia",
    "secret": "yashirin",
    "kim": "kimaytdi",
    "telephone": "telefon",
    "memory": "eslaysizmi",
}
LINK = re.compile(
    r"@|(?:https?://|www\.|t\.me/|telegram\.me/)|\b[\w-]+\.(?:[a-z]{2,24})(?:/|\b)", re.I
)


def payload(kind, game_id):
    value = f"{PREFIXES[kind]}_{game_id}"
    if not isinstance(game_id, int) or game_id <= 0 or len(value) > 64:
        raise ValueError("Invalid private game link")
    return value


def parse_payload(value):
    if not value or len(value) > 64:
        return None
    prefix, separator, number = value.rpartition("_")
    if separator and number.isascii() and number.isdecimal() and 0 < len(number) <= 19:
        kind = next((kind for kind, name in PREFIXES.items() if name == prefix), None)
        if kind and int(number) > 0:
            return kind, int(number)
    return None


def safe_submission(message, *, limit=300):
    value = message.text or message.caption or ""
    entities = (message.entities or []) + (message.caption_entities or [])
    return (
        message.forward_origin is None
        and message.sender_chat is None
        and message.edit_date is None
        and len(value) <= limit
        and not LINK.search(value)
        and not any(
            entity.type in {"url", "text_link", "mention", "text_mention"} for entity in entities
        )
    )


def target_cycle(players, rng=None):
    order = list(players)
    (rng or random).shuffle(order)
    return repair_cycle(order)


def repair_cycle(order):
    return (
        {user: order[(index + 1) % len(order)] for index, user in enumerate(order)}
        if len(order) > 1
        else {}
    )


def matches(word, message):
    needle = normalize_text(word)
    return any(
        token == needle or (len(needle) >= 4 and token.startswith(needle))
        for token in normalize_text(message).split()
    )


def replacement(words, current, previous, rng=None):
    occupied = {normalize_text(word) for word in current.values() if word}
    available = [
        word
        for word in words
        if normalize_text(word) not in occupied and normalize_text(word) != normalize_text(previous)
    ]
    return (rng or random).choice(available) if available else None


def guess_rewards(author, votes, hidden=False, kind="kim"):
    correct = {user: 3 for user, choice in votes.items() if choice == author and user != author}
    author_bonus = (3 if not correct else 0) if kind == "kim" else (2 if correct else 0)
    if author_bonus and not hidden:
        correct[author] = author_bonus
    return correct
