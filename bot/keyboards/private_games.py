from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.games.private_input import payload


def lobby(username, game):
    rows = [
        [
            InlineKeyboardButton(
                text=texts.JOIN_BUTTON,
                url=f"https://t.me/{username}?start={payload(game.game, game.id)}",
            )
        ]
    ]
    if game.game == "secret":
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.SECRET_DURATION.format(hours=hours),
                    callback_data=f"pg:{game.id}:0:h:{hours}",
                )
                for hours in (2, 6, 24)
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def hide(game_id, item):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.PRIVATE_GAME_HIDE, callback_data=f"ph:{game_id}:{item}"
                )
            ]
        ]
    )
