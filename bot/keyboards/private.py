from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts


def add_to_group_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    url = (
        f"https://t.me/{bot_username}?startgroup=add"
        "&admin=restrict_members+delete_messages+pin_messages"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.ADD_TO_GROUP, url=url)]]
    )
