from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.services.settings import CHOICES


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=texts.JOIN_BUTTON, callback_data="join")]]
    )


def settings_keyboard(chat) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{label}: {texts.setting_value(field, getattr(chat, field))}",
                    callback_data=f"sf:{field}",
                )
            ]
            for field, label in texts.SETTING_LABELS.items()
        ]
    )


def setting_choices(field: str) -> InlineKeyboardMarkup:
    rows = []
    for raw in CHOICES.get(field, ()):
        value = (
            raw if field == "penalty_mode" else (raw == "1" if field == "daily_enabled" else raw)
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.setting_value(field, value), callback_data=f"sv:{field}:{raw}"
                )
            ]
        )
    if field in texts.SETTING_PROMPTS:
        rows.append([InlineKeyboardButton(text=texts.CUSTOM_BUTTON, callback_data=f"sp:{field}")])
    rows.append([InlineKeyboardButton(text=texts.BACK_BUTTON, callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
