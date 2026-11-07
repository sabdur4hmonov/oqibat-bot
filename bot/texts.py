"""All bot-facing text, including command descriptions, in Uzbek Latin."""

from html import escape

SLOGAN = "Guruhda oqibat bo‘lsin"
ADD_TO_GROUP = "Botni guruhingizga qo‘shing"
START_DESCRIPTION = "Bot bilan tanishish"
HELP_DESCRIPTION = "Yordam va qo‘llanma"
CONFIG_ERROR = "Sozlamalarda xato bor. .env faylini README bo‘yicha tekshiring."
STARTUP_ERROR = "Bot ishga tushmadi. Sozlamalar, baza va internet aloqasini tekshiring."
CHECK_OK = "Sozlamalar va baza tayyor. Telegram aloqasi tekshirilmadi."


def start_text(first_name: str, instagram_handle: str) -> str:
    return (
        f"Salom, {escape(first_name)}! 👋\n\n"
        f"<b>{SLOGAN}</b>\n"
        "Men Oqibat botman. Guruhingizda do‘stlar bilan aloqani saqlashga yordam beraman.\n"
        "Hozir dastlabki tayyorgarlik bosqichidaman. Guruh o‘yinlari keyinroq qo‘shiladi.\n\n"
        "Yordam: /help\n\n"
        f"Muallif: @{escape(instagram_handle)}"
    )


def help_text(instagram_handle: str) -> str:
    return (
        f"<b>{SLOGAN}</b>\n\n"
        "/start — bot bilan tanishish\n"
        "/help — yordam\n\n"
        "Botni guruhingizga qo‘shish uchun quyidagi tugmani bosing. "
        "Qo‘shishda administrator huquqlarini bering.\n"
        "Guruhga qo‘shilish, vazifalar va o‘yinlar keyingi bosqichlarda qo‘shiladi.\n\n"
        f"Muallif: @{escape(instagram_handle)}"
    )
