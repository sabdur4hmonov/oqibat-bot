"""Category navigation and deterministic daily suggestions."""

from hashlib import sha256

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts

CATEGORIES = {
    "fast": ("duel", "rps", "quiz", "number", "math", "wyr"),
    "word": ("krokodil", "hyj", "kim"),
    "large": ("mafia", "telephone", "memory"),
    "background": ("secret",),
}


def game_button(kind, *, daily=False):
    label = texts.DAILY_GAME if daily else f"{texts.GAME_EMOJIS[kind]} {texts.GAME_NAMES[kind]}"
    return InlineKeyboardButton(text=label, callback_data=f"hg:{kind}")


def hub_keyboard(category=None):
    if category not in CATEGORIES:
        rows = [
            [InlineKeyboardButton(text=label, callback_data=f"hc:{key}")]
            for key, label in texts.HUB_CATEGORIES.items()
        ]
    else:
        rows = [[game_button(kind)] for kind in CATEGORIES[category]]
        rows.append([InlineKeyboardButton(text=texts.HUB_BACK, callback_data="hc:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def daily_keyboard(chat_id, day):
    games = ("quiz", "rps", "number", "math", "krokodil")
    index = int.from_bytes(sha256(f"{chat_id}:{day}".encode()).digest()[:4], "big")
    return InlineKeyboardMarkup(
        inline_keyboard=[[game_button(games[index % len(games)], daily=True)]]
    )
