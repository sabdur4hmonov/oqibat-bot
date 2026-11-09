from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.games.mafia.roles import COMMISSIONER, DOCTOR, DON, MAFIA, MISTRESS, SERIAL, is_mafia


def lobby(username, session_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.MAFIA_JOIN, url=f"https://t.me/{username}?start=mafia_{session_id}"
                )
            ]
        ]
    )


def actions(game, user=None):
    state = game.state
    if state["phase"] == "vote" and user is None:
        operation = "v"
    elif state["phase"] == "night" and str(user) in state["alive"]:
        operation = {
            MAFIA: "m",
            DON: "m",
            DOCTOR: "d",
            COMMISSIONER: "c",
            MISTRESS: "b",
            SERIAL: "s",
        }.get(state["roles"][str(user)])
        if operation is None or (operation == "c" and state["night"]["check"] is not None):
            return None
    else:
        return None
    rows = []
    for target in state["alive"]:
        if operation == "m" and is_mafia(state["roles"][target]):
            continue
        if operation == "c" and target == str(user):
            continue
        if operation in {"b", "s"} and target == str(user):
            continue
        if operation == "b" and target == state.get("last_block"):
            continue
        if operation == "d" and target == str(user) and state["last_doctor_self"]:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=state["players"][target][:40],
                    callback_data=f"mf:{game.id}:{state['round']}:{operation}:{target}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
