"""All bot-facing text, including command descriptions, in Uzbek Latin."""

from html import escape
from zoneinfo import ZoneInfo

SLOGAN = "Guruhda oqibat bo‘lsin"
CARD_BRAND = "OQIBAT"
CARD_WEEKLY_TITLE = "Haftalik top 5"
CARD_GAME_TITLES = {
    "quiz": "Viktorina natijalari",
    "duel": "Duel g‘olibi",
    "krokodil": "Krokodil natijalari",
    "hyj": "Haqiqat yoki jasorat",
    "mafia": "Mafia g‘oliblari",
}
ADD_TO_GROUP = "Botni guruhingizga qo‘shing"
OPEN_WEBAPP = "Ilovani ochish"
CONTENT_DESCRIPTION = "Oqibat matn banklarini tekshirish (internet va .env kerak emas)."
CONTENT_DIRECTORY = "Tekshiriladigan data papkasi"
CONTENT_OK = "[OK] Barcha matn banklari to‘g‘ri. Namunalar jonli kontent o‘rnini bosmaydi."
CONTENT_BAD = "[X] Xatolar bor. CONTENT_GUIDE.md bo‘yicha tuzating va qayta tekshiring."
CONTENT_ERRORS = {
    "schema": (
        "Tuzilma, maydon, noyob key, tur yoki uzunlik noto‘g‘ri. Qo‘llanmadagi shaklni tekshiring."
    ),
    "json": (
        "JSON yoki UTF-8 noto‘g‘ri, yoxud bir obyekt maydoni takrorlangan. UTF-8 BOMsiz saqlang."
    ),
    "unreadable": "Fayl yoki papka o‘qilmadi. Manzil va ruxsatni tekshiring.",
    "missing": "Kerakli bank fayli topilmadi. Bo‘sh bank uchun [] yozing.",
    "unknown": "Bu nomdagi bank tanilmagan. Faqat qo‘llanmadagi olti JSON fayl kerak.",
    "duplicate_text": (
        "Matn boshqa elementni takrorlaydi (harf/apostrof farqi ham hisobga olinadi)."
    ),
    "duplicate_options": "Variantlar takrorlangan yoki faqat bo‘sh joydan iborat.",
    "placeholder": "Faqat kunlik matnda bir marta {group} ishlatish mumkin.",
    "duplicate_key": "Bu key boshqa bankda ham bor. Barcha banklarda noyob key yozing.",
}


def content_count(file, count):
    value = str(count) if count is not None else "?"
    return f"{file}: {value} ta element"


def content_issue(file, code, item):
    location = f"{file}, {item}-element" if item is not None else file
    return f"[X] {location}: {CONTENT_ERRORS[code]}"


WEB_COPY = {
    "title": "Oqibat",
    "tagline": "Guruhingiz bilan birga",
    "read_only": "Bu ilova faqat ko‘rish uchun. O‘zgartirishlar bot orqali qilinadi.",
    "group": "Guruh",
    "group_hint": (
        "Faqat bot biladigan guruhlar chiqadi. Boshqa guruh uchun undagi /help tugmasini oching."
    ),
    "refresh": "Yangilash",
    "privacy": "Ma’lumot va o‘chirish haqida botdagi /maxfiylik buyrug‘ini o‘qing.",
    "profile": "Profilim",
    "leaderboard": "Reyting",
    "achievements": "Yutuqlarim",
    "rules_title": "Qoidalar",
    "rules": (
        "Ishtirok etish ixtiyoriy: /qoshilish bilan qo‘shiling, /chiqish bilan chiqing.\n\n"
        "Kunlik xabardan keyingi ilk qatnashuv +1 ball. Ketma-ket 7 kun +3, 30 kun +10 bonus. "
        "Video vazifasi +15, ovoz yoki rasm +10, matn +5. O‘tkazilgan vazifa odatda −5; "
        "admin tanlagan boshqa jazo ham bo‘lishi mumkin. /sozlamalar ni tekshiring.\n\n"
        "Viktorinada to‘g‘ri javob +3, birinchi javobga yana +2. Duel g‘olibiga +2. "
        "Krokodilda topuvchiga +5, boshlovchiga +3; boshlovchi so‘zni yozsa −3. "
        "Haqiqat javobiga +5, jasoratga vazifa bo‘yicha ball, rad etishga −2.\n\n"
        "Mafia 5–15 kishi bilan: rollar shaxsiy chatda, tunda harakat, kunduzi muhokama va ovoz. "
        "O‘lganlar ovoz bermaydi. G‘olibga +10, tirik qolishga +3. Kengaytirilgan rejimda "
        "8 kishidan Don teng mafia ovozini hal qiladi va komissarga tinch ko‘rinadi; "
        "9 kishidan Ma’shuqa bir harakatni to‘sadi, bir odamni ketma-ket tanlamaydi; "
        "11 kishidan Manyak alohida o‘ynaydi va o‘zi bilan ko‘pi bilan ikki kishi qolsa yutadi. "
        "20 tur yoki 60 daqiqada durang. /stop ni boshlovchi yoki admin ishlatadi.\n\n"
        "Mavsum guruhning mahalliy kalendar oyi bo‘yicha. Eski ballar o‘chmaydi. "
        "Ilovani ochish ball bermaydi va rozilikni o‘zgartirmaydi."
    ),
    "period": "Davr",
    "season": "Joriy mavsum",
    "all_time": "Barcha vaqt",
    "total_points": "Jami ball",
    "achievement_count": "Ochilgan yutuqlar",
    "loading": "Yuklanmoqda…",
    "no_scores": "Hozircha ball yo‘q.",
    "points": "ball",
    "choose_group": "Avval guruhni tanlang.",
    "link_group": "Havoladagi guruh",
    "telegram_only": "Ilovani Telegram ichida botdagi tugma orqali oching.",
    "auth_error": "Telegram tasdiqlovi noto‘g‘ri. Ilovani botdan qayta oching.",
    "expired": "Tasdiqlov eskirgan. Ilovani botdan qayta oching.",
    "bad_request": "So‘rov noto‘g‘ri. Guruh va davrni qayta tanlang.",
    "forbidden": "Bu guruhga ruxsat yo‘q. Guruh a’zosi ekaningizni va bot adminligini tekshiring.",
    "not_found": "Sahifa topilmadi.",
    "busy": "Hozir band. Birozdan keyin qayta urinib ko‘ring.",
    "error": "Ma’lumot yuklanmadi. Keyinroq qayta urinib ko‘ring.",
}
START_DESCRIPTION = "Bot bilan tanishish"
HELP_DESCRIPTION = "Yordam va qo‘llanma"
CONFIG_ERROR = "Sozlamalarda xato bor. .env faylini README bo‘yicha tekshiring."
STARTUP_ERROR = "Bot ishga tushmadi. Sozlamalar, baza va internet aloqasini tekshiring."
CHECK_OK = "Sozlamalar va baza tayyor. Telegram aloqasi tekshirilmadi."
ENV_FILE_MISSING = "[X] .env topilmadi. Avval: Copy-Item .env.example .env, keyin notepad .env."
ENV_FILE_UNREADABLE = (
    "[X] .env o‘qilmadi. Faylga ruxsatni va UTF-8 shaklida saqlanganini tekshiring."
)
ENV_SETTINGS_OK = "[OK] .env va PowerShell muhitidagi sozlamalar to‘g‘ri o‘qildi."
ENV_INVALID_HEADER = "[X] Sozlamalarni tuzating (maxfiy qiymatlar ko‘rsatilmaydi):"
ENV_FIELD_HINTS = {
    "webapp_url": "WEBAPP_URL: o‘z domeningizdagi https://domen.uz/webapp yoki bo‘sh qiymat kerak.",
    "bot_token": "BOT_TOKEN: BotFather bergan tokenni raqam:kalit shaklida to‘liq nusxalang.",
    "bot_username": "BOT_USERNAME: botning Username qiymati kerak, havola emas; oxiri bot bo‘lsin.",
    "instagram_handle": "INSTAGRAM_HANDLE: Instagram nomini yozing, havola emas.",
    "owner_id": "OWNER_ID: o‘zingizning noldan katta raqamli Telegram ID qiymatingizni yozing.",
    "database_url": "DATABASE_URL: sqlite+aiosqlite yoki postgresql+asyncpg ulanish manzili kerak.",
    "log_level": "LOG_LEVEL: DEBUG, INFO, WARNING, ERROR yoki CRITICAL bo‘lsin.",
    "environment": "ENVIRONMENT: mahalliy sinov uchun development, server uchun production.",
    "db_pool_size": "DB_POOL_SIZE: 10 dan 20 gacha butun son yozing.",
    "use_webhook": "USE_WEBHOOK: mahalliy sinov uchun false yozing.",
    "webhook_url": "WEBHOOK_URL: webhook uchun to‘liq HTTPS manzil va yo‘l kerak.",
    "webhook_secret": "WEBHOOK_SECRET: webhook uchun maxfiy harf, raqam, _ yoki - qiymat kerak.",
    "webhook_host": "WEBHOOK_HOST: serverning mahalliy manzilini yozing, masalan 127.0.0.1.",
    "webhook_port": "WEBHOOK_PORT: 1 dan 65535 gacha port raqamini yozing.",
    "result_cards_enabled": "RESULT_CARDS_ENABLED: rasmli natijalar uchun true, matn uchun false.",
}
ENV_RUNTIME_HINT = (
    "ENVIRONMENT/DATABASE_URL/USE_WEBHOOK/WEBHOOK_URL/WEBHOOK_SECRET ni tekshiring. "
    "production uchun PostgreSQL kerak. Webhook uchun HTTPS yo‘l va "
    "1–256 ta harf, raqam, _ yoki - dan tuzilgan maxfiy kalit kerak. "
    "Mahalliy sinovda ENVIRONMENT=development va USE_WEBHOOK=false qoldiring."
)
ENV_TOKEN_BAD = (
    "[X] BOT_TOKEN shakli noto‘g‘ri yoki namuna token qolgan. BotFather tokenini yozing."
)
ENV_TOKEN_OK = "[OK] BOT_TOKEN shakli to‘g‘ri. Tokenning haqiqiyligi Telegramda tekshiriladi."
ENV_TELEGRAM_SKIPPED = "[!] Token tuzatilmaguncha Telegram tekshiruvi bajarilmaydi."
ENV_GETME_OK = "[OK] Telegram getMe javob berdi: token qabul qilindi."
ENV_USERNAME_OK = "[OK] Telegramdagi bot nomi BOT_USERNAME bilan mos."
ENV_USERNAME_BAD = (
    "[X] BOT_USERNAME token egasining Username qiymatiga mos emas. "
    "BotFatherdagi bot nomini .env ga yozing; oddiy ko‘rinadigan ismni yozmang."
)
ENV_TOKEN_REJECTED = (
    "[X] Telegram tokenni qabul qilmadi. BotFatherdagi joriy tokenni qayta nusxalang."
)
ENV_TELEGRAM_NETWORK = "[X] Telegramga ulanib bo‘lmadi. Internet va Telegramga kirishni tekshiring."
ENV_TELEGRAM_TIMEOUT = "[X] Telegram javobi kechikdi. Internetni tekshirib, qayta urinib ko‘ring."
ENV_TELEGRAM_FAILED = (
    "[X] Telegram tekshiruvi bajarilmadi. Tokenni tekshirib, keyinroq qayta urining."
)
ENV_DB_OK = "[OK] Bazaga ulanish va SELECT 1 tekshiruvi muvaffaqiyatli."
ENV_SCHEMA_OK = "[OK] Botga kerakli jadval va ustunlar mavjud."
ENV_SCHEMA_BAD = "[X] Bazada jadval yoki ustunlar yetishmaydi. Avval: alembic upgrade head."
ENV_DB_MISSING = "[X] SQLite baza fayli topilmadi. Loyiha papkasida: alembic upgrade head."
ENV_DB_FAILED = (
    "[X] Bazaga ulanib bo‘lmadi. DATABASE_URL, faylga ruxsat yoki PostgreSQL serveri, "
    "baza nomi va kirish ma'lumotlarini tekshiring."
)
ENV_DB_TIMEOUT = "[X] Baza javobi kechikdi. Server, tarmoq va DATABASE_URL ni tekshiring."
ENV_CHECK_OK = "[OK] Barcha tekshiruvlar o‘tdi. Botni ishga tushirish: python -m bot."
ENV_CHECK_FAILED = "[X] Tekshiruv tugadi. Yuqoridagi xatolarni tuzatib, buyruqni qayta bajaring."
ENV_CHECK_CANCELLED = "Tekshiruv to‘xtatildi."


def env_retry_after(seconds):
    return f"[X] Telegram vaqtincha kutishni so‘radi. {seconds} soniyadan keyin qayta tekshiring."


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
MEMBER_CHECK_FAILED = (
    "Guruhdagi a'zoligingizni tekshirib bo‘lmadi. "
    "Guruh a'zosi ekaningizni tekshirib, keyinroq qayta urinib ko‘ring."
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
    "maxfiylik": "Ma’lumotlar maxfiyligi",
    "yutuqlar": "Mening yutuqlarim",
    "help": HELP_DESCRIPTION,
    "qoshilish": "O‘yinga qo‘shilish",
    "chiqish": "O‘yindan chiqish",
    "sozlamalar": "Guruh sozlamalari (admin)",
    "vazifa": "Hozir vazifa berish (admin)",
    "men": "Mening ballarim",
    "top": "Guruh reytingi",
    "duel": "Bot tashlaydigan zar dueli",
    "viktorina": "Besh savolli viktorina",
    "tanla": "Ikki variantdan birini tanlash",
    "krokodil": "So‘z topish o‘yini",
    "hyj": "Haqiqat yoki jasorat",
    "mafia": "Mafia: 5–15 kishilik o‘yin",
    "stop": "O‘yinni to‘xtatish",
}
GAME_JOIN_FIRST = "O‘yin uchun bot admin bo‘lishi va siz /qoshilish bilan qo‘shilishingiz kerak."
GAME_BUSY = "Bu turdagi o‘yin allaqachon ketmoqda. Yakunini kuting yoki /stop yuboring."
GAME_CANCELLED = "O‘yin to‘xtatildi. 🛑"
GAME_TIMEOUT = "O‘yin kutish muddati tugadi. Qayta boshlashingiz mumkin."
GAME_RESTARTED = "Bot qayta ishga tushdi. Kechirasiz, bu o‘yinni qayta boshlang."
GAME_BUTTON_EXPIRED = "Bu tugma siz uchun emas yoki uning vaqti tugagan."
GAME_NO_CONTENT = "Bu o‘yin uchun savollar hali kiritilmagan."
NO_ACTIVE_GAME = "Hozir faol o‘yin yo‘q."
STOP_DENIED = "O‘yinni faqat uni boshlagan a'zo yoki administrator to‘xtata oladi."
DUEL_INVALID_TARGET = "O‘zingizdan boshqa, /qoshilish bilan qo‘shilgan a'zoni tanlang."
DUEL_ACCEPT = "Duelni qabul qilish"
QUIZ_START = (
    "🧠 Viktorina boshlanmoqda! 5 savol, har biriga 30 soniya. To‘g‘ri javob +3, birinchi +2."
)
WYR_START = "🤔 Qaysi birini tanlaysiz? Ovoz berish uchun 60 soniya."
WYR_FINISHED = "Tanlov yakunlandi. Natijalar so‘rovnomada! ✅"
KROK_START = "🐊 Krokodil boshlanmoqda! Boshlovchi so‘zni tugma orqali yashirin ko‘radi."
KROK_NEED_PLAYERS = "Krokodil uchun kamida ikki a'zo /qoshilish bilan qo‘shilsin."
KROK_SEE = "So‘zni ko‘rish"
KROK_SKIP = "So‘zni almashtirish"
KROK_HOST_ONLY = "So‘zni faqat hozirgi boshlovchi ko‘ra oladi."
KROK_NO_SKIPS = "Bir turda faqat ikki marta so‘z almashtirish mumkin."
KROK_SKIPPED = "So‘z almashtirilmoqda. So‘zni ko‘rish tugmasini yana bosing."
HYJ_TRUTH = "Haqiqat"
HYJ_DARE = "Jasorat"
HYJ_REFUSE = "Rad etish (−2)"
HYJ_TARGET_ONLY = "Bu tugmani faqat tanlangan ishtirokchi bosa oladi."
HYJ_INVALID_TARGET = "Javob berilgan a'zo /qoshilish bilan o‘yinga qo‘shilgan bo‘lsin."
MAFIA_JOIN = "Mafiaga qo‘shilish (shaxsiy chat)"
MAFIA_JOINED = "Mafiaga qo‘shildingiz! O‘yin boshlanishini guruhda kuting."
MAFIA_LOBBY_CLOSED = "Mafia kutish muddati yopiq, to‘lgan yoki bu havola eskirgan."
MAFIA_ALREADY_PLAYING = "Siz boshqa Mafia o‘yinidasiz. Bir paytda faqat bitta o‘yinda qatnashing."
MAFIA_OPT_IN = "Avval o‘sha guruhda /qoshilish yuboring, keyin havolani yana bosing."
MAFIA_TOO_FEW = "Mafia bekor qilindi: kamida 5 ta tayyor ishtirokchi kerak."
MAFIA_DELIVERY_FAILED = "Mafia bekor qilindi: rollarni yetkazib bo‘lmadi. Keyinroq qayta boshlang."
MAFIA_RESTART = (
    "Bot qayta ishga tushdi. Kechirasiz, Mafia bekor qilindi. /mafia bilan qayta boshlang."
)
MAFIA_STALE = "Bu Mafia tugmasi eskirgan, siz uchun emas yoki bu bosqichda ishlamaydi."
MAFIA_CHOICE_SAVED = "Tanlov saqlandi."
MAFIA_CHECK_AT_DAWN = "Tanlov saqlandi. Tekshiruv javobi tongda shaxsiy doskada chiqadi."
MAFIA_IS_MAFIA = "Tekshiruv: bu o‘yinchi — mafia."
MAFIA_NOT_MAFIA = "Tekshiruv: bu o‘yinchi mafia emas."
MAFIA_ROLE_NAMES = {
    "mafia": "Mafia",
    "doctor": "Doktor",
    "commissioner": "Komissar",
    "town": "Tinch aholi",
    "don": "Don",
    "mistress": "Ma’shuqa",
    "manyak": "Manyak",
}
MAFIA_OUTCOMES = {
    "town": "Tinch aholi g‘alaba qozondi!",
    "mafia": "Mafia g‘alaba qozondi!",
    "manyak": "Manyak yakka g‘alaba qozondi!",
    "draw": "Durang: vaqt yoki 20 tur chegarasi tugadi.",
}


def mafia_event(state):
    event = state.get("last_event") or {}
    if len(event.get("victims", [])) > 1:
        return "\n".join(
            f"{mention(int(user), state['players'][user])} o‘yindan chiqdi. "
            f"Roli: <b>{MAFIA_ROLE_NAMES[state['roles'][user]]}</b>."
            for user in event["victims"]
        )
    victim = event.get("victim")
    if victim:
        who = mention(int(victim), state["players"][victim])
        role = MAFIA_ROLE_NAMES[event["role"]]
        saved = " Doktor boshqa nishonni saqlab qoldi." if event.get("saved") else ""
        return f"{who} o‘yindan chiqdi. Roli: <b>{role}</b>.{saved}"
    if event.get("saved"):
        return "Tong otdi: doktor nishondagi o‘yinchini saqlab qoldi. 🩺"
    if event.get("kind") == "night":
        return "Tong otdi: bu kecha hech kim o‘yindan chiqmadi."
    if event.get("kind") == "vote":
        return "Ovozlar teng yoki ovoz yo‘q: hech kim chiqarilmadi."
    return ""


def mafia_group(game):
    state = game.state
    removed = state.get("removed", [])
    notice = (
        (
            "Shaxsiy aloqasi yo‘q yoki chiqib ketganlar ro‘yxatdan olindi: "
            + ", ".join(escape(name[:24]) for name in removed)
            + ".\n"
        )
        if removed
        else ""
    )
    phase = state["phase"]
    if phase in {"lobby", "preparing"}:
        players = "\n".join(
            f"{i}. {mention(int(user), name)}"
            for i, (user, name) in enumerate(state["players"].items(), 1)
        )
        status = (
            "Kutish: 90 soniya. 5–15 kishi. Guruhda /qoshilish yuboring, "
            "so‘ng havoladan shaxsiy chatga o‘ting."
            if phase == "lobby"
            else "Shaxsiy aloqa va rollar tayyorlanmoqda. Hali tun boshlanmadi."
        )
        mode = (
            "\nKengaytirilgan rejim: 8+ Don, 9+ Ma’shuqa (tinch jamoa), 11+ Manyak (yakka)."
            if state.get("extended_roles")
            else ""
        )
        return f"🎭 <b>Mafia</b> — {len(state['players'])}/15\n{notice}{status}{mode}\n\n{players}"
    if phase == "done":
        outcome = MAFIA_OUTCOMES.get(state.get("winner"), "Mafia to‘xtatildi. Ball berilmaydi.")
        roles = "\n".join(
            f"{mention(int(user), state['players'][user])} — {MAFIA_ROLE_NAMES[role]}"
            for user, role in state.get("roles", {}).items()
        )
        return f"🎭 {outcome}\n{mafia_event(state)}\n\n{roles}"
    status = {
        "night": "🌙 Tun: 60 soniya. Harakatlar shaxsiy chatdagi tugmalarda.",
        "discussion": "☀️ Muhokama: 90 soniya. Guruhda gaplashing.",
        "vote": "🗳 Ovoz berish: 60 soniya. Faqat tirik o‘yinchilar; ovozni almashtirish mumkin.",
    }[phase]
    text = (
        f"🎭 Mafia — {state['round']}-tur\n{mafia_event(state)}\n{status}\n"
        f"Tirik: {len(state['alive'])}."
    )
    if phase == "vote":
        from bot.games.mafia.engine import tally

        counts = tally(state)
        text += "\n\n" + "\n".join(
            f"{mention(int(user), state['players'][user])}: {counts.get(user, 0)}"
            for user in state["alive"]
        )
    return text


def mafia_proposal(game, user, proposed):
    role = proposed[user]
    team = ", ".join(
        escape(game.state["players"][who]) + (" (Don)" if value == "don" else "")
        for who, value in proposed.items()
        if value in {"mafia", "don"}
    )
    return (
        f"🎭 Mafia #{game.id}. Tayyorlash {game.state['setup_attempt']}.\n"
        f"Dastlabki rol: <b>{MAFIA_ROLE_NAMES[role]}</b>.\n"
        + (f"Mafia jamoasi: {team}.\n" if role in {"mafia", "don"} else "")
        + "Hali harakat qilmang. Hamma tayyor bo‘lgach rol tasdiqlanadi; "
        "yangilansa oldingisi bekor."
    )


def mafia_private(game, user):
    from bot.games.mafia.engine import tally

    state, user = game.state, str(user)
    role = state["roles"][user]
    text = (
        f"🎭 Mafia #{game.id} — {escape(state.get('chat_title', ''))}\n"
        f"Sizning rolingiz: <b>{MAFIA_ROLE_NAMES[role]}</b>.\n"
    )
    if user not in state["alive"]:
        return text + "Siz o‘yindan chiqdingiz. Harakat yoki ovoz bera olmaysiz."
    text += f"{state['round']}-tur. "
    if state["phase"] == "night":
        if role in {"mafia", "don"}:
            team = [
                mention(int(who), state["players"][who]) + (" (Don)" if value == "don" else "")
                for who, value in state["roles"].items()
                if value in {"mafia", "don"}
            ]
            text += (
                "Mafia jamoasi: "
                + ", ".join(team)
                + ".\nNishonni tanlang. Ovoz yo‘q bo‘lsa hujum yo‘q.\n"
            )
            if role == "don":
                text += (
                    "Teng ovozda sizning tanlovingiz hal qiladi. "
                    "Komissarga mafia bo‘lib ko‘rinmaysiz.\n"
                )
            counts = tally(state, mafia=True)
            text += "\n".join(
                f"{mention(int(who), state['players'][who])}: {count}"
                for who, count in sorted(counts.items())
            )
        elif role == "doctor":
            text += "Kimni saqlaysiz? O‘zingizni ketma-ket ikki kecha saqlay olmaysiz."
        elif role == "commissioner":
            if "mistress" in state["roles"].values():
                text += (
                    "Bir kishini tekshiring. Tanlovingiz bloklanishi mumkin; "
                    "javob tongda shu yerda chiqadi."
                )
            else:
                text += "Bir kishini tekshiring. Javob faqat sizga oynachada chiqadi."
        elif role == "mistress":
            text += (
                "Siz tinch jamoada: bir kishining tungi harakatini to‘sing. "
                "Ketma-ket bir nishon mumkin emas."
            )
        elif role == "manyak":
            text += (
                "Siz yakka o‘ynaysiz. Tunda bir nishonni tanlang; "
                "tirik qolib, ko‘pi bilan yana bir kishi qolsa yutasiz."
            )
        else:
            text += "Tongni kuting. Sizda tungi harakat yo‘q."
    else:
        text += "Muhokama va kunduzgi ovoz berish guruhda."
    checked = state.get("last_check")
    if role == "commissioner" and checked and checked["actor"] == user:
        result = (
            "Harakatingiz to‘sildi."
            if checked["is_mafia"] is None
            else MAFIA_IS_MAFIA
            if checked["is_mafia"]
            else MAFIA_NOT_MAFIA
        )
        target = mention(int(checked["target"]), state["players"][checked["target"]])
        text += f"\n{checked['round']}-tun: {target}. {result}"
    return text


def mafia_end_dm(game, user):
    points_note = (
        "\nTirik qolganlarga +3 ball."
        if game.state.get("winner") == "draw"
        else "\nG‘olib tomonga +10, oxirigacha tirik qolganlarga +3."
    )
    return (
        f"🎭 Mafia #{game.id} yakunlandi. "
        + MAFIA_OUTCOMES.get(game.state.get("winner"), "O‘yin bekor qilindi. Ball berilmaydi.")
        + (points_note if game.state.get("winner") else "")
    )


def hyj_choice(game):
    state = game.state
    return (
        f"🎭 {mention(state['target'], state['name'])}, haqiqat yoki jasorat?\n"
        "Tanlash uchun 90 soniya. Faqat siz tugmani bosa olasiz. Rad etish: −2 ball."
    )


def hyj_truth(game):
    state = game.state
    return (
        f"💬 {mention(state['target'], state['name'])}, haqiqat:\n{escape(state['question'])}\n\n"
        "30 daqiqada matn yoki ovozli xabar bilan javob bering. Javob uchun +5 ball."
    )


def hyj_dare(game):
    state = game.state
    end = game.phase_deadline_at.astimezone(ZoneInfo(state.get("display_tz", "Asia/Tashkent")))
    return (
        f"🎯 {mention(state['target'], state['name'])}, jasorat:\n{escape(state['prompt'])}\n\n"
        f"Muddati: {end:%d.%m %H:%M}. Rad etish: faqat −2, cheklash yoki chiqarish yo‘q."
    )


def hyj_result(game):
    result = game.state.get("result")
    who = mention(game.state["target"], game.state["name"])
    ending = {
        "truth_done": "haqiqatga javob berdi. +5 ball! ✅",
        "dare_done": "jasoratni bajardi! Vazifa ballari berildi. ✅",
        "refused": "rad etdi. Faqat −2 ball; cheklash yoki chiqarish yo‘q.",
        "dare_missed": "jasorat muddati tugadi. Guruhning vazifa jazosi qo‘llanadi.",
        "dare_cancelled": "jasorat bekor qilindi. Ball jazosi yo‘q.",
        "timeout": "uchun o‘yin muddati tugadi. Qo‘shimcha jazo yo‘q.",
        "opted_out": "o‘yindan chiqdi. Vazifa bekor qilindi, ball jazosi yo‘q.",
    }
    return f"🎭 {who} {ending.get(result, 'uchun o‘yin yakunlandi.')}"


def krok_word(word):
    return f"Sizning so‘zingiz: {word}"


def krok_board(game, final=False):
    state = game.state
    last = state.get("last_result", {})
    lines = []
    if last.get("kind") == "guess":
        guesser = mention(last["guesser"], state["names"].get(str(last["guesser"]), "Ishtirokchi"))
        lines.append(
            f"✅ {guesser} topdi: <b>{escape(last['word'])}</b>. Topganga +5, boshlovchiga +3."
        )
    elif last.get("kind") == "reveal":
        lines.append(f"Boshlovchi so‘zni yozdi: {escape(last['word'])}. −3 ball; yangi so‘z! 🙈")
    elif last.get("kind") == "timeout":
        lines.append(f"⏰ Vaqt tugadi. So‘z: <b>{escape(last['word'])}</b>.")
    if final:
        lines.append("🏆 Krokodil yakunlandi! 10 tur o‘ynaldi.")
        scores = sorted(state.get("scores", {}).items(), key=lambda pair: (-pair[1], int(pair[0])))
        lines.extend(
            f"{i}. {mention(int(user), state['names'].get(user, 'Ishtirokchi'))} — {score} ball"
            for i, (user, score) in enumerate(scores[:15], 1)
        )
    else:
        host = mention(state["host"], state["names"].get(str(state["host"]), "Ishtirokchi"))
        lines.append(
            f"🐊 Krokodil {state['round']}/10. Boshlovchi: {host}.\n"
            f"Topish uchun 3 daqiqa. Almashtirish qoldi: {2 - state['skips']}.\n"
            "Boshlovchi so‘zni yozmasdan tushuntirsin, boshqalar guruhga taxmin yozsin."
        )
    return "\n\n".join(lines)


def duel_lobby(game):
    state = game.state
    starter = mention(game.started_by, state["names"][str(game.started_by)])
    target = (
        mention(state["target"], state["names"][str(state["target"])])
        if state.get("target")
        else "Istalgan ishtirokchi"
    )
    return (
        f"{state['emoji']} {starter} duelga chaqirdi!\n{target} qabul qilsin.\n"
        "Zar turini boshlovchi tanlaydi. Kutish: 90 soniya."
    )


def duel_rolling(game):
    state = game.state
    first = mention(game.started_by, state["names"][str(game.started_by)])
    second = mention(state["opponent"], state["names"][str(state["opponent"])])
    return (
        f"{state['emoji']} Duel, {state['round']}-urinish. Teng bo‘lsa qayta tashlayman.\n"
        f"Birinchi zar: {first}\nIkkinchi zar: {second}"
    )


def duel_result(game):
    state = game.state
    winner = mention(state["winner"], state["names"][str(state["winner"])])
    return (
        f"{state['emoji']} Natija: {state['values'][0]} : {state['values'][1]}\n"
        f"{winner} g‘olib! +2 ball. 🏆"
    )


def quiz_board(game, final=False):
    state = game.state
    heading = (
        "🏆 Viktorina yakunlandi!"
        if final
        else f"🧠 Viktorina: {state.get('question_index', 0) + 1}/5"
    )
    scores = sorted(state.get("scores", {}).items(), key=lambda pair: (-pair[1], int(pair[0])))
    rows = [
        f"{i}. {mention(int(user), state['names'].get(user, 'Ishtirokchi'))} — {score} ball"
        for i, (user, score) in enumerate(scores[:15], 1)
    ]
    return heading + "\n" + ("\n".join(rows) if rows else "Hali to‘g‘ri javob yo‘q.")


QUIET_ASSIGN = "Hozir tinch vaqt. Vazifani tinch vaqt tugagach bering."
PENDING_CHALLENGE = "Bu guruhda hali bajarilmagan vazifa bor. Avval u yakunlansin."
NO_CHALLENGE_CANDIDATE = "Mos ishtirokchi yoki vazifa topilmadi. /qoshilish bilan qo‘shiling."
CHALLENGE_SEND_FAILED = "Vazifani yuborib bo‘lmadi. Keyinroq qayta urinib ko‘ring."
CHALLENGE_ARGUMENTS = "Masalan: /vazifa video, /vazifa ovoz, /vazifa surat yoki /vazifa matn."
NO_SCORES = "Hali ballar yo‘q."


def mention(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={user_id}">{escape(name)}</a>'


def challenge_post(user_id: int, name: str, prompt: str, deadline, tz: str) -> str:
    end = deadline.astimezone(ZoneInfo(tz)).strftime("%d.%m %H:%M")
    return f"🎯 {mention(user_id, name)}, sizga vazifa!\n{escape(prompt)}\n\nMuddati: {end}"


def challenge_done(user_id: int, name: str, delta: int) -> str:
    return f"Barakalla, {mention(user_id, name)}! Vazifa bajarildi. +{delta} ball! ✅"


def challenge_missed(user_id: int, mode: str) -> str:
    penalty = "Ball jazosi yo‘q." if mode == "off" else "−5 ball."
    return (
        f"{mention(user_id, 'Do‘stimiz')}, vazifa muddati tugadi. {penalty} Keyingi safar albatta!"
    )


def debtors_suffix(debtors) -> str:
    if not debtors:
        return ""
    names = ", ".join(mention(user_id, name) for user_id, name in debtors)
    return f"\n\n🙂 Bugungi qarzdor do‘stlarimiz: {names}. Keyingi safar birga bajaramiz!"


def my_stats(name: str, total: int, done: int, missed: int) -> str:
    return (
        f"{escape(name)}\n⭐ Jami: {total} ball\n"
        f"✅ Bajarilgan vazifalar: {done}\n⌛ O‘tkazilgan: {missed}"
    )


def leaderboard(weekly, overall) -> str:
    def rows(items):
        return (
            "\n".join(
                f"{i}. {mention(user_id, name)} — {points} ball"
                for i, (user_id, name, points) in enumerate(items, 1)
            )
            or NO_SCORES
        )

    return f"🏆 <b>Joriy mavsum</b>\n{rows(weekly)}\n\n⭐ <b>Barcha vaqt</b>\n{rows(overall)}"


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
    "mafia_delete_dead_messages": "Mafia: o‘yindan chiqqanlarning xabarini o‘chirish",
    "extended_roles": "Mafia: kengaytirilgan rollar (keyingi o‘yin)",
}
SETTING_PROMPTS = {
    "tz": "Vaqt mintaqasini kiriting, masalan: Asia/Tashkent. Shu xabarga javob yozing.",
    "daily_time": "Kunlik xabar vaqtini HH:MM shaklida kiriting (09:00). Shu xabarga javob yozing.",
    "quiet_start": "Tinch vaqt boshlanishini HH:MM shaklida kiriting. Shu xabarga javob yozing.",
    "quiet_end": "Tinch vaqt tugashini HH:MM shaklida kiriting. Shu xabarga javob yozing.",
    "kick_after_misses": "1 dan 100 gacha son kiriting. Shu xabarga javob yozing.",
}


def setting_value(field: str, value) -> str:
    if field in {"daily_enabled", "mafia_delete_dead_messages", "extended_roles"}:
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


def group_help(instagram_handle=None) -> str:
    commands = "\n".join(
        f"/{command} — {description}" for command, description in GROUP_COMMANDS.items()
    )
    details = (
        "\n\n🎯 Vazifalar: faqat /qoshilish bilan rozilik berganlar orasidan. "
        "/chiqish istalgan payt ishlaydi.\n"
        "🎲 /duel ni javob tarzida yoki ochiq yuboring; zarni bot tashlaydi.\n"
        "🧠 /viktorina: 5 savol, har biriga 30 soniya.\n"
        "🤔 /tanla: bir daqiqalik ochiq tanlov.\n"
        "🐊 /krokodil: yashirin so‘z, 10 tur, har biri 3 daqiqa.\n"
        "🎭 /hyj: haqiqatga 30 daqiqa, jasoratga 1 soat; rad etish −2.\n"
        "🌙 /mafia: 5–15 kishi, 90 soniyalik havola orqali qo‘shilish. "
        "Hamma botni shaxsiy chatda ochishi kerak.\n"
        "🛑 /stop: boshlovchi yoki admin. Duelni tanlash uchun doskasiga javob bering.\n"
        "⏰ Kunlik xabar 0–15 daqiqaga tarqatiladi; haftalik xulosa yakshanba 20:00–21:00. "
        "Tinch vaqtda avtomatik xabar/vazifalar kutiladi."
    )
    footer = f"\n\nMuallif: @{escape(instagram_handle)}" if instagram_handle else ""
    return f"<b>{SLOGAN}!</b>\n\n" + commands + details + footer


def daily_post(template: str, group: str) -> str:
    return escape(template).replace("{group}", escape(group))


def start_text(first_name: str, instagram_handle: str) -> str:
    return (
        f"Salom, {escape(first_name)}! 👋\n\n"
        f"<b>{SLOGAN}</b>\n"
        "Men Oqibat botman. Guruhingizda do‘stlar bilan aloqani saqlashga yordam beraman.\n"
        "Vazifalar, viktorina va zar duellarida birga qatnashing!\n\n"
        "Yordam: /help\n\n"
        f"Muallif: @{escape(instagram_handle)}"
    )


def help_text(instagram_handle: str) -> str:
    return (
        "/start — bot bilan tanishish\n/help — yordam\n\n"
        "/maxfiylik — ma’lumotlar haqida\n/malumotlarimni_ochir — shaxsiy chatda o‘chirish\n"
        "/stats — faqat bot egasi uchun\n\n"
        "Botni guruhga administrator qilib qo‘shing. Guruh buyruqlari:\n\n"
        + group_help(instagram_handle)
    )


def weekly_summary(week, data, instagram_handle, *, compact=False):
    def name(value):
        return value[:24] + "…" if compact and len(value) > 24 else value

    title = f"🏆 <b>Haftalik oqibat</b> — {week:%d.%m.%Y} haftasi\n{SLOGAN}!"
    top = (
        "\n".join(
            f"{i}. {mention(user, name(label))} — {points} ball"
            for i, (user, label, points) in enumerate(data["top"], 1)
        )
        or NO_SCORES
    )
    active = data["active"]
    activity = (
        f"🔥 Eng faol: {mention(active[0], name(active[1]))} — "
        f"{active[2]} ta muvaffaqiyatli ishtirok."
        if active
        else "🔥 Bu haftada hali ball olgan ishtirok yo‘q."
    )
    return (
        f"{title}\n\n{top}\n\n{activity}\n"
        f"🎯 Hafta vazifalari: bajarildi {data['done']}, o‘tkazildi {data['missed']}. "
        f"Hozir kutilmoqda: {data['pending']}.\n\nMuallif: @{escape(instagram_handle)}"
    )


OWNER_STATS_DESCRIPTION = "Bot egasi uchun holat"
PRIVACY_DESCRIPTION = "Ma’lumotlar maxfiyligi"
ERASE_DESCRIPTION = "Ma’lumotlarimni o‘chirish"
PRIVACY = (
    "🔐 <b>Maxfiylik</b>\n"
    "Telegram ID, ism va username; guruh sozlamalari, qo‘shilish roziligi, oxirgi faollik, "
    "vazifa/o‘yin natijalari va ballar saqlanadi. Ular o‘yinlar, reyting va vazifalar uchun kerak. "
    "Oddiy yozishmalar, surat, ovoz yoki video fayllari saqlanmaydi. "
    "Faol o‘yin holati tanlangan javoblar yoki ismlarni saqlashi mumkin.\n"
    "Rozilikdan /chiqish bilan chiqing. Shaxsiy chatda /malumotlarimni_ochir orqali "
    "ma’lumotlaringizni tasdiqlab o‘chiring. Avval yuborilgan Telegram xabarlari va "
    "operatorning tashqi zaxira nusxalari bu buyruq bilan o‘chmaydi."
)
OWNER_ONLY = "Bu buyruq faqat bot egasi uchun."
ERASE_CONFIRM = "Ha, ma’lumotlarimni o‘chiring"
ERASED_NAME = "O‘chirilgan ishtirokchi"
ERASE_WARNING = (
    "Ballar, vazifalar, guruhlardagi qatnashish va o‘yinlardagi shaxsiy izlaringiz o‘chadi. "
    "Bog‘liq faol o‘yinlar tugaydi; umumiy o‘yin yozuvlari shaxssizlanadi. "
    "Qaytarib bo‘lmaydi. Tugma 5 daqiqa amal qiladi. Telegramdagi eski xabarlar va "
    "tashqi zaxiralar alohida boshqariladi. Tasdiqlaysizmi?"
)
ERASE_WORKING = "So‘rov tekshirilmoqda."
ERASE_EXPIRED = "Tasdiq eskirgan yoki sizga tegishli emas. Buyruqni qayta yuboring."
ERASE_DONE = "Ma’lumotlaringiz o‘chirildi. Qayta foydalanish uchun /start yuboring."


def owner_stats(data):
    games = (
        "\n".join(f"{escape(kind)}: {count}" for kind, count in sorted(data["games"].items()))
        or NO_SCORES
    )
    return (
        f"📊 <b>Bot holati</b>\nFaol guruhlar: {data['groups']}\n"
        f"Rozilik bergan a’zolar: {data['opted']}\n"
        f"Oxirgi 24 soatda faol: {data['active']}\n"
        f"7 kunda boshlangan o‘yinlar:\n{games}\n"
        f"Yuborish navbati: {data['queue']}\n"
        f"Oxirgi tekshiruv: {data['tick'] * 1000:.1f} ms"
    )


SEASON_TITLE = "Mavsum chempionlari"
ACHIEVEMENTS = {
    "first_task": "Ilk bajarilgan vazifa",
    "first_video": "Ilk davra videosi",
    "ten_krok": "10 ta Krokodil topish",
    "first_mafia_win": "Ilk Mafia g‘alabasi",
    "streak7": "7 kunlik qatnashish",
    "streak30": "30 kunlik qatnashish",
}


def season_month(day):
    return f"{day.year}-yil {day.month}-oy"


def season_result(day, rows):
    winners = (
        "\n".join(
            f"{index}. {mention(user, name[:32])} — {points} ball"
            for index, (user, name, points) in enumerate(rows[:5], 1)
        )
        or NO_SCORES
    )
    return f"🏆 <b>{SEASON_TITLE}</b> — {season_month(day)}\n{winners}"


def achievement_list(rows):
    unlocked = {row.key for row in rows}
    return "🏅 <b>Yutuqlarim</b>\n" + "\n".join(
        ("✅ " if key in unlocked else "🔒 ") + label for key, label in ACHIEVEMENTS.items()
    )


def achievement_batch(items):
    grouped = {}
    for user, name, key in items:
        if key in ACHIEVEMENTS:
            grouped.setdefault((user, name), []).append(ACHIEVEMENTS[key])
    return "🏅 <b>Yangi yutuqlar!</b>\n" + "\n".join(
        f"{mention(user, name[:32])}: {', '.join(labels)}"
        for (user, name), labels in grouped.items()
    )


def card_points(points):
    return f"{points} ball"


def card_watermark(instagram):
    return f"@{instagram}"


def card_week(week):
    return f"{week:%d.%m.%Y} haftasi · {SLOGAN}"


def game_card_data(game):
    if game.status != "finished":
        return None
    state = game.state
    rows = []
    if game.game in {"quiz", "krokodil"}:
        scores = sorted(state.get("scores", {}).items(), key=lambda pair: (-pair[1], int(pair[0])))
        rows = [
            (state.get("names", {}).get(user, "Ishtirokchi"), score)
            for user, score in scores[:5]
            if score > 0
        ]
    elif game.game == "duel" and state.get("winner"):
        rows = [(state["names"].get(str(state["winner"]), "Ishtirokchi"), 2)]
    elif game.game == "hyj" and state.get("result") in {"truth_done", "dare_done"}:
        points = 5 if state["result"] == "truth_done" else state.get("result_points", 0)
        rows = [(state["name"], points)] if points else []
    elif game.game == "mafia" and state.get("winner") in {"town", "mafia", "manyak"}:
        from bot.games.mafia.roles import side

        for user, role in state.get("roles", {}).items():
            if side(role) == state["winner"] and user not in state.get("forfeited", []):
                rows.append((state["players"][user], 10 + (3 if user in state["alive"] else 0)))
        rows.sort(key=lambda pair: -pair[1])
    return {"title": CARD_GAME_TITLES[game.game], "rows": rows[:5]} if rows else None


def game_card_caption(game):
    return f"🏆 {CARD_GAME_TITLES[game.game]}"
