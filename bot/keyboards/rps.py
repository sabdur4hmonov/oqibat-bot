from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.games.rps import MOVES


def game_keyboard(game):
    prefix = f"rp:{game.id}:{game.state['round']}:"
    if game.state["phase"] == "lobby":
        buttons = [InlineKeyboardButton(text=texts.RPS_ACCEPT, callback_data=prefix + "a")]
    elif game.state["phase"] == "choosing":
        buttons = [
            InlineKeyboardButton(text=texts.RPS_MOVES[move], callback_data=prefix + move)
            for move in MOVES
        ]
    else:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
