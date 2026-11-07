"""All bot-facing text, including command descriptions, in Uzbek Latin."""

from html import escape

SLOGAN = "Guruhda oqibat bo‘lsin"
ADD_TO_GROUP = "Botni guruhingizga qo‘shing"
START_DESCRIPTION = "Bot bilan tanishish"
HELP_DESCRIPTION = "Yordam va qo‘llanma"
CONFIG_ERROR = "Sozlamalarda xato bor. .env faylini README bo‘yicha tekshiring."
STARTUP_ERROR = "Bot ishga tushmadi. Sozlamalar, baza va internet aloqasini tekshiring."
CHECK_OK = "Sozlamalar va baza tayyor. Telegram aloqasi tekshirilmadi."
JOIN_BUTTON = "O‘yinga qo‘shilish"
WELCOME_GROUP = (
    "<b>Guruhda oqibat bo‘lsin!</b> 👋\n"
    "O‘yinlar va vazifalarda qatnashish uchun quyidagi tugmani bosing. "
    "Istalgan vaqtda /chiqish bilan chiqishingiz mumkin."
)
NEED_ADMIN = (
    "Ishlashim uchun meni guruh administratori qiling: guruh nomi → "
    "Tahrirlash → Administratorlar → Administrator qo‘shish. "
    "Xabarlarni o‘chirish, a'zolarni cheklash va xabarlarni qadash huquqlarini bering."
)
JOINED = "Qo‘shildingiz! Vazifa va o‘yinlarda qatnashishingiz mumkin. ✅"
OPTED_OUT = (
    "O‘yindan chiqdingiz. Endi sizga yangi vazifa berilmaydi. /qoshilish bilan qayta qo‘shiling."
)
ADMINS_ONLY = "Bu sozlamalarni faqat guruh administratori o‘zgartira oladi."
ADMIN_CHECK_FAILED = "Administratorlarni tekshirib bo‘lmadi. Birozdan keyin qayta urinib ko‘ring."
SETTINGS_TITLE = "⚙️ Guruh sozlamalari"
SETTINGS_SAVED = "Saqlandi. ✅"
SETTINGS_INVALID = "Qiymat noto‘g‘ri. Ko‘rsatilgan shaklda qayta yuboring."
SETTINGS_EXPIRED = "Sozlash vaqti tugadi. /sozlamalar bilan qayta boshlang."
BACK_BUTTON = "← Orqaga"
CUSTOM_BUTTON = "Qiymat kiritish"
YES_NO = {True: "Yoqilgan", False: "O‘chirilgan"}
PENALTY_NAMES = {
    "off": "Jazo yo‘q",
    "points": "Ball ayirish",
    "mute": "Ovozini cheklash",
    "kick": "Guruhdan chiqarish",
}
GROUP_COMMANDS = {
    "help": HELP_DESCRIPTION,
    "qoshilish": "O‘yinga qo‘shilish",
    "chiqish": "O‘yindan chiqish",
    "sozlamalar": "Guruh sozlamalari (admin)",
}
SETTING_LABELS = {
    "tz": "Vaqt mintaqasi",
    "daily_enabled": "Kunlik xabar",
    "daily_time": "Kunlik xabar vaqti",
    "challenges_per_day": "Kuniga vazifalar soni",
    "challenge_hours": "Vazifa muddati (soat)",
    "penalty_mode": "Bajarilmagan vazifa jazosi",
    "mute_days": "Cheklash muddati (kun)",
    "kick_after_misses": "Nechta o‘tkazishdan keyin chiqarish",
    "quiet_start": "Tinch vaqt boshlanishi",
    "quiet_end": "Tinch vaqt tugashi",
}
SETTING_PROMPTS = {
    "tz": "Vaqt mintaqasini kiriting, masalan: Asia/Tashkent. Shu xabarga javob yozing.",
    "daily_time": "Kunlik xabar vaqtini HH:MM shaklida kiriting (09:00). Shu xabarga javob yozing.",
    "quiet_start": "Tinch vaqt boshlanishini HH:MM shaklida kiriting. Shu xabarga javob yozing.",
    "quiet_end": "Tinch vaqt tugashini HH:MM shaklida kiriting. Shu xabarga javob yozing.",
    "kick_after_misses": "1 dan 100 gacha son kiriting. Shu xabarga javob yozing.",
}


def setting_value(field: str, value) -> str:
    if field == "daily_enabled":
        return YES_NO[value]
    if field == "penalty_mode":
        return PENALTY_NAMES[value]
    if field in {"daily_time", "quiet_start", "quiet_end"}:
        return value.strftime("%H:%M")
    return escape(str(value))


def setting_prompt(field: str, user) -> str:
    return (
        f'<a href="tg://user?id={user.id}">{escape(user.first_name)}</a>, {SETTING_PROMPTS[field]}'
    )


def group_help() -> str:
    return (
        "<b>Guruhda oqibat bo‘lsin!</b>\n\n"
        "/qoshilish — o‘yinga qo‘shilish\n/chiqish — o‘yindan chiqish\n"
        "/sozlamalar — guruh sozlamalari (faqat admin)\n"
        "Vazifalar va o‘yinlar keyingi bosqichlarda qo‘shiladi."
    )


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
        "Guruhda /qoshilish — qo‘shilish, /chiqish — chiqish, /sozlamalar — admin sozlamalari.\n"
        "Vazifalar va o‘yinlar keyinroq qo‘shiladi.\n\n"
        f"Muallif: @{escape(instagram_handle)}"
    )
