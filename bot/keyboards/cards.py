from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts


def story_keyboard(source, keyboard=None):
    rows = list(keyboard.inline_keyboard) if keyboard else []
    rows.append([InlineKeyboardButton(text=texts.STORY_BUTTON, callback_data=f"sc:{source}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
