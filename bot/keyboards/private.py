from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot import texts


def add_to_group_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    url = (
        f"https://t.me/{bot_username}?startgroup=add"
        "&admin=restrict_members+delete_messages+pin_messages"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.ADD_TO_GROUP, url=url)]]
    )


def private_keyboard(settings):
    keyboard = add_to_group_keyboard(settings.bot_username)
    if settings.webapp_url:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.OPEN_WEBAPP, web_app=WebAppInfo(url=settings.webapp_url)
                )
            ]
        )
    return keyboard


def group_keyboard(settings, chat_id):
    keyboard = add_to_group_keyboard(settings.bot_username)
    if settings.webapp_url:
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=texts.OPEN_WEBAPP,
                    url=f"https://t.me/{settings.bot_username}?startapp={chat_id}",
                )
            ]
        )
    return keyboard
