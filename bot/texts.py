"""All bot-facing text, including command descriptions, in Uzbek Latin."""

from html import escape
from zoneinfo import ZoneInfo

from bot.utils.presentation import compact_html

GAME_STYLE = {
    "duel": ("🎲", "Zar dueli", "#f5b94c"),
    "quiz": ("🧠", "Viktorina", "#8c8bff"),
    "wyr": ("🤔", "Tanla", "#e987b1"),
    "krokodil": ("🐊", "Krokodil", "#3ac99b"),
    "hyj": ("🎯", "Haqiqat yoki jasorat", "#ed9474"),
    "mafia": ("🎭", "Mafia", "#af91e8"),
    "rps": ("🪨", "Tosh–qaychi–qog‘oz", "#82b7e8"),
    "number": ("🔢", "Son topish", "#61c5dc"),
    "math": ("🧮", "Tezkor matematika", "#e9c566"),
    "secret": ("🕵️", "Yashirin topshiriq", "#64b7a8"),
    "kim": ("💬", "Kim aytdi?", "#ed9ab8"),
    "telephone": ("☎️", "Ovozli buzilgan telefon", "#f0a96c"),
    "memory": ("📸", "Eslaysizmi?", "#9ba9f5"),
}
GAME_EMOJIS = {key: value[0] for key, value in GAME_STYLE.items()}
GAME_NAMES = {key: value[1] for key, value in GAME_STYLE.items()}
MEDALS = ("🥇", "🥈", "🥉")


def game_title(kind):
    return f"{GAME_EMOJIS[kind]} <b>{GAME_NAMES[kind]}</b>"


def progress_bar(done, total):
    total = max(1, total)
    done = min(total, max(0, done))
    filled = done * 5 // total
    return "▰" * filled + "▱" * (5 - filled) + f" {done}/{total}"


def game_progress(game):
    state, kind = (game.state, game.game)
    if kind == "quiz":
        return (min(5, state.get("question_index", 0) + 1), 5)
    if kind in {"math", "krokodil", "mafia"}:
        return (state.get("round", 0), {"math": 5, "krokodil": 10, "mafia": 20}[kind])
    if kind == "number":
        return (state.get("attempts", 0), 15)
    if kind == "telephone":
        return (state.get("turn", 0), max(1, len(state.get("order", state.get("players", {})))))
    if kind in {"kim", "memory"}:
        return (state.get("round", 0), max(1, len(state.get("order", state.get("players", {})))))
    if kind == "secret":
        return (sum(state.get("successes", {}).values()), max(1, len(state.get("players", {})) * 3))
    return (1 if game.status == "finished" else 0, 1)


def board_layout(game, body):
    title = game_title(game.game)
    if body.startswith(title + "\nHolat:"):
        return body
    if body.startswith(title):
        body = body[len(title) :].lstrip(" \n")
    state, phase = (game.state, game.state.get("phase", "lobby"))
    status = {
        "lobby": "Davra yig‘ilyapti",
        "preparing": "Tayyorgarlik",
        "sending": "Tayyorgarlik",
        "collect": "Shaxsiy javoblarni kutamiz",
        "prompting": "Shaxsiy topshiriqlar yo‘lda",
        "done": "Davra yakunlandi",
        "hunt": "Ov davom etyapti",
        "guess": "Taxmin vaqti",
        "turn": "Navbat davom etyapti",
        "night": "🌙 Tun",
        "discussion": "☀️ Kunduzi · suhbat",
        "vote": "☀️ Kunduzi · ovoz berish",
    }.get(phase, "O‘yin davom etyapti")
    if game.status == "cancelled":
        status = "Davra to‘xtadi"
    elif game.status == "finished":
        status = "Davra yakunlandi"
    deadline = game.phase_deadline_at
    at = (
        deadline.astimezone(ZoneInfo(state.get("display_tz", "Asia/Tashkent"))).strftime("%H:%M")
        if deadline
        else None
    )
    timing = f"⏳ {at} gacha" if at else "⏳ Bu bosqich yakunlandi"
    if phase in {
        "sending",
        "preparing",
        "truth_sending",
        "answer_sending",
        "turn_sending",
        "chain_reveal",
        "reveal_sending",
        "prompting",
    } and game.status not in {"finished", "cancelled"}:
        timing = "⏳ Bosqich tayyor bo‘lishini kutamiz"
    lines = [title, f"Holat: {status}", progress_bar(*game_progress(game)), timing]
    known = state.get("players", state.get("names", {}))
    if not isinstance(known, dict):
        known = {str(user): state.get("names", {}).get(str(user), "Davradosh") for user in known}
    if not known and state.get("name"):
        known = {str(state.get("target", game.started_by)): state["name"]}
    if known:
        lines.extend(["", "Davradoshlar:"])
        mark = "✅" if game.status in {"finished", "cancelled"} or phase == "lobby" else "⏳"
        lines.extend(f"{mark} {escape(str(name)[:24])}" for name in list(known.values())[:20])
        if len(known) > 20:
            lines.append(f"Yana {len(known) - 20} davradosh")
    if game.status == "finished":
        scores = state.get("scores", {})
        if scores:
            lines.extend(["", "Natijalar:"])
            ordered = sorted(scores.items(), key=lambda pair: (-pair[1], int(pair[0])))[:10]
            lines.extend(
                (
                    format(MEDALS[index] if index < 3 else str(index + 1) + ".", "")
                    + " "
                    + format(
                        escape(
                            str(
                                known.get(
                                    str(user), state.get("names", {}).get(str(user), "Davradosh")
                                )
                            )[:24]
                        ),
                        "",
                    )
                    + " · "
                    + format(score, "")
                    + " ball"
                    for index, (user, score) in enumerate(ordered)
                )
            )
        elif state.get("winner") and str(state["winner"]) in known:
            lines.append(f"{MEDALS[0]} {escape(str(known[str(state['winner'])])[:24])}")
        elif game.game in {"mafia", "hyj"}:
            card = game_card_data(game)
            if card:
                lines.extend(
                    f"{MEDALS[index] if index < 3 else str(index + 1) + '.'} "
                    f"{escape(str(name)[:24])} · {score} ball"
                    for index, (name, score) in enumerate(card["rows"])
                )
    lines.extend(["", body])
    return compact_html("\n".join(lines), limit=4096)


MAFIA_ROLE_CARDS = {
    "mafia": (
        "🔪",
        "Tunda jamoangiz bilan nishon tanlaysiz.",
        "Mafia ustunligini ta’minlang; manyak qolmasin.",
    ),
    "don": (
        "🕴",
        "Mafia teng ovozida tanlovingiz hal qiladi; komissarga tinch " + "ko‘rinasiz.",
        "Mafia jamoasi bilan yuting; manyak qolmasin.",
    ),
    "doctor": (
        "💊",
        "Har tun bir odamni himoya qilasiz.",
        "Mafia va manyakni yo‘qotishda tinch jamoaga yordam bering.",
    ),
    "commissioner": (
        "🔍",
        "Tunda bir odamni tekshirasiz.",
        "Mafia va manyakni yo‘qotishda tinch jamoaga yordam bering.",
    ),
    "town": (
        "🏘",
        "Kunduz suhbat va ovoz bilan jamoaga yordam berasiz.",
        "Mafia va manyak qolmasin.",
    ),
    "mistress": (
        "🌹",
        "Tunda bir odamning harakatini to‘sasiz.",
        "Tinch jamoa bilan yuting; mafia va manyak qolmasin.",
    ),
    "manyak": (
        "🗡",
        "Yakka o‘ynab, tunda bir nishonni tanlaysiz.",
        "Tirik qoling: yoningizda ko‘pi bilan bir odam qolsin.",
    ),
}


def mafia_role_card(role):
    icon, description, goal = MAFIA_ROLE_CARDS[role]
    return f"{icon} <b>{MAFIA_ROLE_NAMES[role]}</b>\n{description}\nMaqsad: {goal}\n"


SLOGAN = "Guruhda oqibat bo‘lsin"
CARD_BRAND = "OQIBAT"
CARD_WEEKLY_TITLE = "Haftalik top 5"
CARD_GAME_TITLES = {
    "quiz": "Viktorina natijalari",
    "duel": "Duel g‘olibi",
    "rps": "Tosh–qaychi–qog‘oz g‘olibi",
    "number": "Son topish g‘olibi",
    "math": "Tezkor matematika natijalari",
    "krokodil": "Krokodil natijalari",
    "hyj": "Haqiqat yoki jasorat",
    "mafia": "Mafia g‘oliblari",
}
ADD_TO_GROUP = "Botni guruhingizga qo‘shing"
OPEN_WEBAPP = "Ilovani ochish"
CONTENT_DESCRIPTION = "Oqibat matn banklarini tekshirish (internet va .env kerak emas)."
CONTENT_DIRECTORY = "Tekshiriladigan data papkasi"
CONTENT_OK = "[OK] Barcha matn banklari to‘g‘ri. Namunalar jonli kontent " + "o‘rnini bosmaydi."
CONTENT_BAD = "[X] Xatolar bor. CONTENT_GUIDE.md bo‘yicha tuzating va qayta " + "tekshiring."
CONTENT_ERRORS = {
    "schema": "Tuzilma, maydon, noyob key, tur yoki uzunlik noto‘g‘ri. "
    + "Qo‘llanmadagi shaklni tekshiring.",
    "json": "JSON yoki UTF-8 noto‘g‘ri, yoxud bir obyekt maydoni "
    + "takrorlangan. UTF-8 BOMsiz saqlang.",
    "unreadable": "Fayl yoki papka o‘qilmadi. Manzil va ruxsatni tekshiring.",
    "missing": "Kerakli bank fayli topilmadi. Bo‘sh bank uchun [] yozing.",
    "unknown": "Bu nomdagi bank tanilmagan. Faqat qo‘llanmadagi JSON bank " + "fayllari kerak.",
    "duplicate_text": "Matn boshqa elementni takrorlaydi (harf/apostrof farqi ham "
    + "hisobga olinadi).",
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
    "group_hint": "Faqat bot biladigan guruhlar chiqadi. Boshqa guruh uchun undagi "
    + "/help tugmasini oching.",
    "refresh": "Yangilash",
    "privacy": "Ma’lumot va o‘chirish haqida botdagi /maxfiylik buyrug‘ini o‘qing.",
    "profile": "Profilim",
    "leaderboard": "Reyting",
    "achievements": "Yutuqlarim",
    "rules_title": "Qoidalar",
    "rules": "Ishtirok etish ixtiyoriy: /qoshilish bilan qo‘shiling, /chiqish "
    + "bilan chiqing.\n\nKunlik xabardan keyingi ilk qatnashuv +1 ball. "
    + "Ketma-ket 7 kun +3, 30 kun +10 bonus. Video vazifasi +15, ovoz "
    + "yoki rasm +10, matn +5. O‘tkazilgan vazifa odatda −5; admin "
    + "tanlagan boshqa jazo ham bo‘lishi mumkin. /sozlamalar ni "
    + "tekshiring.\n\nViktorinada to‘g‘ri javob +3, birinchi javobga yana"
    + " +2. Duel g‘olibiga +2. Tosh–qaychi–qog‘oz (/tqq) ikki kishi "
    + "bilan: har kim yashirin tanlaydi, ikkala tanlovdan keyin natija "
    + "ochiladi. Tosh qaychini, qaychi qog‘ozni, qog‘oz toshni yutadi. "
    + "G‘olibga +2, durangda ball yo‘q. Son topish (/sontop): 1–100, 15"
    + " urinish, 3 daqiqa; topuvchiga +3. Tezkor matematika "
    + "(/matematika): 5 savol, har biri 20 soniya, birinchi to‘g‘ri "
    + "javobga +2; har savolda bir urinish. /oyinlar da ro‘yxat bor. "
    + "Krokodilda topuvchiga +5, boshlovchiga +3; boshlovchi so‘zni "
    + "yozsa −3. Haqiqat javobiga +5, jasoratga vazifa bo‘yicha ball, "
    + "rad etishga −2.\n\nMafia 5–15 kishi bilan: rollar shaxsiy chatda, "
    + "tunda harakat, kunduzi muhokama va ovoz. O‘lganlar ovoz "
    + "bermaydi. G‘olibga +10, tirik qolishga +3. Kengaytirilgan "
    + "rejimda 8 kishidan Don teng mafia ovozini hal qiladi va "
    + "komissarga tinch ko‘rinadi; 9 kishidan Ma’shuqa bir harakatni "
    + "to‘sadi, bir odamni ketma-ket tanlamaydi; 11 kishidan Manyak "
    + "alohida o‘ynaydi va o‘zi bilan ko‘pi bilan ikki kishi qolsa "
    + "yutadi. 20 tur yoki 60 daqiqada durang. /stop ni boshlovchi yoki"
    + " admin ishlatadi.\n\nYashirin topshiriq (/yashirin): 3–20 kishi, "
    + "2/6/24 soatlik fon o‘yini. Nishon maxfiy so‘zni guruhda aytsa "
    + "ovchiga +10 (ko‘pi bilan 3 marta); /fosh javob bilan: to‘g‘ri "
    + "+5, xato −2 va 1 soat kutish, jami 3 gumon.\nKim aytdi? "
    + "(/kimaytdi): 4–12 kishi, shaxsiy javob <=300 belgi, 5 daqiqa. "
    + "Anonim javobga 30 soniya taxmin; to‘g‘ri +3, hech kim topmasa "
    + "muallifga +3.\nTelefon (/telefon): 4–10 kishi; navbatda 2 daqiqa,"
    + " ovoz <=30 soniya. Keyingi odamga faqat oldingi ovoz, oxirgi "
    + "odamdan matn; yakunda zanjir ochiladi. Topshirgan, materiali "
    + "yashirilmagan odamga +3.\nEslaysizmi? (/eslaysizmi): 3–10 kishi, "
    + "5 daqiqada bitta shaxsiy surat. Guruhda spoiler, 30 soniya "
    + "taxmin, keyin yuboruvchi va izoh ochiladi. To‘g‘ri topuvchiga "
    + "+3; kamida bir kishi topsa yuboruvchiga +2.\nBu o‘yinlarga "
    + "lobbydagi shaxsiy havola bilan rozilik berib kirasiz. Mafia "
    + "bilan birga faqat bitta faol shaxsiy o‘yinda bo‘lish mumkin. "
    + "Admin materialni yashirsa muallifning shu material bali bekor "
    + "qilinadi. Media o‘chirish huquqi yo‘qolsa admin uni qo‘lda "
    + "o‘chirishi kerak. Asosiy o‘yin bilan Yashirin birga yuradi; fon "
    + "o‘yinini to‘xtatish uchun uning doskasiga /stop bilan javob "
    + "bering.\n\nMavsum guruhning mahalliy kalendar oyi bo‘yicha. Eski "
    + "ballar o‘chmaydi. Ilovani ochish ball bermaydi va rozilikni "
    + "o‘zgartirmaydi.",
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
    "forbidden": "Bu guruhga ruxsat yo‘q. Guruh a’zosi ekaningizni va bot "
    + "adminligini tekshiring.",
    "not_found": "Sahifa topilmadi.",
    "busy": "Hozir band. Birpasdan so‘ng yana urinib ko‘ring.",
    "error": "Ma’lumot yuklanmadi. Birpasdan so‘ng yana urinib ko‘ring.",
}
START_DESCRIPTION = "Davrani boshlaymiz"
HELP_DESCRIPTION = "Davra uchun yordam"
CONFIG_ERROR = "Sozlamalarda xato bor. .env faylini README bo‘yicha tekshiring."
STARTUP_ERROR = "Bot ishga tushmadi. Sozlamalar, baza va internet aloqasini " + "tekshiring."
CHECK_OK = "Sozlamalar va baza tayyor. Telegram aloqasi tekshirilmadi."
ENV_FILE_MISSING = (
    "[X] .env topilmadi. Avval: Copy-Item .env.example .env, keyin " + "notepad .env."
)
ENV_FILE_UNREADABLE = (
    "[X] .env o‘qilmadi. Faylga ruxsatni va UTF-8 shaklida " + "saqlanganini tekshiring."
)
ENV_SETTINGS_OK = "[OK] .env va PowerShell muhitidagi sozlamalar to‘g‘ri o‘qildi."
ENV_INVALID_HEADER = "[X] Sozlamalarni tuzating (maxfiy qiymatlar ko‘rsatilmaydi):"
ENV_FIELD_HINTS = {
    "webapp_url": "WEBAPP_URL: o‘z domeningizdagi https://domen.uz/webapp yoki "
    + "bo‘sh qiymat kerak.",
    "bot_token": "BOT_TOKEN: BotFather bergan tokenni raqam:kalit shaklida to‘liq " + "nusxalang.",
    "bot_username": "BOT_USERNAME: botning Username qiymati kerak, havola emas; oxiri"
    + " bot bo‘lsin.",
    "instagram_handle": "INSTAGRAM_HANDLE: Instagram nomini yozing, havola emas.",
    "owner_id": "OWNER_ID: o‘zingizning noldan katta raqamli Telegram ID "
    + "qiymatingizni yozing.",
    "database_url": "DATABASE_URL: sqlite+aiosqlite yoki postgresql+asyncpg ulanish "
    + "manzili kerak.",
    "log_level": "LOG_LEVEL: DEBUG, INFO, WARNING, ERROR yoki CRITICAL bo‘lsin.",
    "environment": "ENVIRONMENT: mahalliy sinov uchun development, server uchun " + "production.",
    "db_pool_size": "DB_POOL_SIZE: 10 dan 20 gacha butun son yozing.",
    "use_webhook": "USE_WEBHOOK: mahalliy sinov uchun false yozing.",
    "webhook_url": "WEBHOOK_URL: webhook uchun to‘liq HTTPS manzil va yo‘l kerak.",
    "webhook_secret": "WEBHOOK_SECRET: webhook uchun maxfiy harf, raqam, _ yoki - "
    + "qiymat kerak.",
    "webhook_host": "WEBHOOK_HOST: serverning mahalliy manzilini yozing, masalan " + "127.0.0.1.",
    "webhook_port": "WEBHOOK_PORT: 1 dan 65535 gacha port raqamini yozing.",
    "result_cards_enabled": "RESULT_CARDS_ENABLED: rasmli natijalar uchun true, matn uchun false.",
}
ENV_RUNTIME_HINT = (
    "ENVIRONMENT/DATABASE_URL/USE_WEBHOOK/WEBHOOK_URL/WEBHOOK_SECRET "
    + "ni tekshiring. production uchun PostgreSQL kerak. Webhook uchun "
    + "HTTPS yo‘l va 1–256 ta harf, raqam, _ yoki - dan tuzilgan maxfiy"
    + " kalit kerak. Mahalliy sinovda ENVIRONMENT=development va "
    + "USE_WEBHOOK=false qoldiring."
)
ENV_TOKEN_BAD = (
    "[X] BOT_TOKEN shakli noto‘g‘ri yoki namuna token qolgan. " + "BotFather tokenini yozing."
)
ENV_TOKEN_OK = "[OK] BOT_TOKEN shakli to‘g‘ri. Tokenning haqiqiyligi Telegramda " + "tekshiriladi."
ENV_TELEGRAM_SKIPPED = "[!] Token tuzatilmaguncha Telegram tekshiruvi bajarilmaydi."
ENV_GETME_OK = "[OK] Telegram getMe javob berdi: token qabul qilindi."
ENV_USERNAME_OK = "[OK] Telegramdagi bot nomi BOT_USERNAME bilan mos."
ENV_USERNAME_BAD = (
    "[X] BOT_USERNAME token egasining Username qiymatiga mos emas. "
    + "BotFatherdagi bot nomini .env ga yozing; oddiy ko‘rinadigan "
    + "ismni yozmang."
)
ENV_TOKEN_REJECTED = (
    "[X] Telegram tokenni qabul qilmadi. BotFatherdagi joriy tokenni " + "qayta nusxalang."
)
ENV_TELEGRAM_NETWORK = (
    "[X] Telegramga ulanib bo‘lmadi. Internet va Telegramga kirishni " + "tekshiring."
)
ENV_TELEGRAM_TIMEOUT = (
    "[X] Telegram javobi kechikdi. Internetni tekshirib, yana urinib " + "ko‘ring."
)
ENV_TELEGRAM_FAILED = (
    "[X] Telegram tekshiruvi bajarilmadi. Tokenni tekshirib, keyinroq" + " qayta urining."
)
ENV_DB_OK = "[OK] Bazaga ulanish va SELECT 1 tekshiruvi muvaffaqiyatli."
ENV_SCHEMA_OK = "[OK] Botga kerakli jadval va ustunlar mavjud."
ENV_SCHEMA_BAD = "[X] Bazada jadval yoki ustunlar yetishmaydi. Avval: alembic " + "upgrade head."
ENV_DB_MISSING = "[X] SQLite baza fayli topilmadi. Loyiha papkasida: alembic " + "upgrade head."
ENV_DB_FAILED = (
    "[X] Bazaga ulanib bo‘lmadi. DATABASE_URL, faylga ruxsat yoki "
    + "PostgreSQL serveri, baza nomi va kirish ma'lumotlarini "
    + "tekshiring."
)
ENV_DB_TIMEOUT = "[X] Baza javobi kechikdi. Server, tarmoq va DATABASE_URL ni " + "tekshiring."
ENV_CHECK_OK = "[OK] Barcha tekshiruvlar o‘tdi. Botni ishga tushirish: python -m bot."
ENV_CHECK_FAILED = (
    "[X] Tekshiruv tugadi. Yuqoridagi xatolarni tuzatib, buyruqni " + "qayta bajaring."
)
ENV_CHECK_CANCELLED = "Tekshiruv to‘xtatildi."


def env_retry_after(seconds):
    return f"[X] Telegram vaqtincha kutishni so‘radi. {seconds} soniyadan keyin qayta tekshiring."


JOIN_BUTTON = "O‘yinga qo‘shilish"
WELCOME_GROUP = (
    "<b>Guruhda oqibat bo‘lsin!</b> 👋\nO‘yinlar va vazifalarda "
    + "qatnashish uchun quyidagi tugmani bosing. Istalgan vaqtda "
    + "/chiqish bilan chiqishingiz mumkin."
)
NEED_ADMIN = (
    "Ishlashim uchun meni guruh admini qiling: guruh nomi → "
    + "Tahrirlash → Administratorlar → Administrator qo‘shish. "
    + "Xabarlarni o‘chirish, a'zolarni cheklash va xabarlarni qadash "
    + "huquqlarini bering."
)
MEMBER_CHECK_FAILED = (
    "Guruhdagi a'zoligingizni tekshirib bo‘lmadi. Guruh a'zosi "
    + "ekaningizni tekshirib, keyinroq yana urinib ko‘ring."
)
JOINED = "Davraga xush kelibsiz! Vazifa va o‘yinlarga tayyorsiz. ✅"
OPTED_OUT = (
    "O‘yindan chiqdingiz. Endi sizga yangi vazifa berilmaydi. "
    + "/qoshilish bilan qayta qo‘shiling."
)
ADMINS_ONLY = "Bu sozlamalarni faqat guruh admini o‘zgartiradi."
ADMIN_CHECK_FAILED = "Adminlarni tekshira olmadim. Birpasdan so‘ng yana urinib ko‘ring."
SETTINGS_TITLE = "⚙️ Guruh sozlamalari"
SETTINGS_SAVED = "Tayyor, saqlandi! ✅"
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
    "tqq": "Tosh–qaychi–qog‘oz dueli",
    "sontop": "Yashirin sonni birga topish",
    "matematika": "Tezkor matematik savollar",
    "oyinlar": "Barcha o‘yinlar ro‘yxati",
    "viktorina": "Besh savolli viktorina",
    "tanla": "Ikki variantdan birini tanlash",
    "krokodil": "So‘z topish o‘yini",
    "hyj": "Haqiqat yoki jasorat",
    "mafia": "Mafia: 5–15 kishilik o‘yin",
    "yashirin": "Yashirin topshiriq: fon o‘yini",
    "fosh": "Gumondagi ovchiga javoban fosh qilish",
    "kimaytdi": "Anonim javob muallifini topish",
    "telefon": "Ovozli buzilgan telefon",
    "eslaysizmi": "Suratni kim yuborganini topish",
    "stop": "O‘yinni to‘xtatish",
}
GROUP_MENU = ("oyinlar", "qoshilish", "men", "top", "yutuqlar", "sozlamalar", "stop", "help")
HUB_CATEGORIES = {
    "fast": "Tez o‘yinlar",
    "word": "So‘z o‘yinlari",
    "large": "Katta o‘yinlar",
    "background": "Fon o‘yini",
}
HUB_BACK = "← Barcha toifalar"
HUB_INTRO = (
    "🎲 <b>Davra qizisinmi?</b>\nToifani tanlang, keyin o‘yinni bosing.\n"
    "Guruhda avval /qoshilish. /help da barcha buyruq va qoidalar bor."
)
HUB_GROUP_ONLY = "Davrani guruhda ochamiz! Guruhda /oyinlar yuboring."
DAILY_GAME = "🎲 Bugungi o‘yin"
SETUP_STEPS = (
    "⚙️ 1/3 · Kunlik post qachon kelsin?\nGuruhning mahalliy vaqtini tanlang.",
    "⚙️ 2/3 · Kuniga nechta vazifa beray?\n0 — vazifalarsiz davra.",
    "⚙️ 3/3 · Bajarilmagan vazifaga qanday yo‘l tutamiz?\n"
    "Jazosiz yoki ball; mute/kick uchun botga cheklash huquqi kerak.",
)
SETUP_VALUES = {
    "off": "Jazosiz",
    "points": "−5 ball",
    "mute": "Vaqtincha cheklash",
    "kick": "Chiqarish",
}
SETUP_FULL = "Barcha sozlamalar"
SETUP_DONE = "Tayyor! Davra sizniki. ✅\nIstalgan payt /sozlamalar bilan o‘zgartiring."
WELCOME_GROUP += "\n\n" + SETUP_STEPS[0]

GAME_JOIN_FIRST = (
    "O‘yin uchun bot admin bo‘lishi va siz /qoshilish bilan " + "qo‘shilishingiz kerak."
)
GAME_BUSY = "Bu o‘yin bilan davra qizib turibdi! Yakunini kuting yoki /stop " + "yuboring."
GAME_CANCELLED = "Davra to‘xtadi. 🛑"
GAME_TIMEOUT = "O‘yin kutish muddati tugadi. Yana bir davra boshlash mumkin!"
GAME_RESTARTED = "Bot qayta ishga tushdi. Kechirasiz, bu o‘yinni qayta boshlang."
GAME_BUTTON_EXPIRED = "Bu tugma sizga mos emas yoki eskirgan. Yangi doskani oching."
GAME_NO_CONTENT = "Bu o‘yin uchun savollar hali kiritilmagan."
NO_ACTIVE_GAME = "Davra hali ochilmagan. /oyinlar dan tanlaymizmi?"
STOP_DENIED = "O‘yinni faqat uni boshlagan a'zo yoki administrator to‘xtata oladi."
DUEL_INVALID_TARGET = "O‘zingizdan boshqa, /qoshilish bilan qo‘shilgan a'zoni tanlang."
DUEL_ACCEPT = "Duelni qabul qilish"
RPS_ACCEPT = "O‘yinni qabul qilish"
GAME_CATALOG_DESCRIPTION = "O‘yinlar ro‘yxati"
GAME_CATALOG = (
    "🎮 <b>Oqibat o‘yinlari</b>\n\n"
    + GAME_EMOJIS["number"]
    + (" /sontop — 1–100 orasidagi son. O‘yin xabariga javob bering; " + "topuvchiga +3.\n")
    + GAME_EMOJIS["math"]
    + (" /matematika — 5 tezkor savol, tugmalar orqali javob, har bir " + "g‘olibga +2.\n")
    + GAME_EMOJIS["rps"]
    + " /tqq — ikki kishilik yashirin tosh–qaychi–qog‘oz, g‘olibga +2.\n"
    + GAME_EMOJIS["duel"]
    + " /duel — zarni bot tashlaydi; g‘olibga +2.\n"
    + GAME_EMOJIS["quiz"]
    + " /viktorina — 5 bilim savoli.\n"
    + GAME_EMOJIS["wyr"]
    + " /tanla — ikki variantli umumiy tanlov.\n"
    + GAME_EMOJIS["krokodil"]
    + " /krokodil — yashirin so‘zni toping.\n"
    + GAME_EMOJIS["hyj"]
    + " /hyj — haqiqat yoki jasorat.\n"
    + GAME_EMOJIS["mafia"]
    + " /mafia — 5–15 kishi, rollar shaxsiy chatda.\n"
    + GAME_EMOJIS["secret"]
    + (
        " /yashirin — 3–20 kishi, 2/6/24 soatlik fon o‘yini; topish +10. "
        + "/fosh ni gumondagi ovchiga javoban: to‘g‘ri +5, xato −2.\n"
    )
    + GAME_EMOJIS["kim"]
    + " /kimaytdi — 4–12 kishi, shaxsiy matn va anonim muallif taxmini.\n"
    + GAME_EMOJIS["telephone"]
    + (" /telefon — 4–10 kishi, <=30 soniyalik ovozlar zanjiri va " + "yakuniy matn.\n")
    + GAME_EMOJIS["memory"]
    + (
        " /eslaysizmi — 3–10 kishi, shaxsiy suratlar, spoiler va "
        + "yuboruvchi taxmini.\n\nGuruhda bot admin bo‘lsin, avval /qoshilish"
        + " bilan qo‘shiling. Bitta asosiy o‘yin, alohida Yashirin fon "
        + "o‘yini va zar duellari yurishi mumkin. Yangi o‘yinlarga faqat "
        + "lobbydagi shaxsiy havoladan rozilik bilan kiring. Mafia bilan "
        + "birga bir odamga bitta faol shaxsiy kontekst. Materiallar "
        + "guruhga chiqadi; media uchun botning o‘chirish huquqi kerak. "
        + "Boshlovchi yoki admin /stop bilan to‘xtatadi. /help da batafsil "
        + "yordam."
    )
)
QUICK_RESET = (
    "O‘yin bekor qilindi. Bot/guruh holati yoki yetkazish muddati "
    + "o‘zgardi. Yangi davrani boshlang."
)
QUICK_STARTER_LEFT = (
    "Boshlovchi o‘yindan chiqdi. O‘yin bekor qilindi; oldin olingan " + "ballar saqlanadi."
)
MATH_ALREADY_TRIED = "Bu savolda urinib bo‘ldingiz. Keyingisida ko‘rishamiz!"
MATH_CORRECT = "Topdingiz! +2 ball. ✅"
MATH_WRONG = "Bu safar mos kelmadi. Shu savolda bitta urinish bor; keyingisini" + " kutamiz."


def math_expression(item):
    operation = {"+": "+", "-": "−", "*": "×"}[item["op"]]
    return f"{item['a']} {operation} {item['b']}"


def quick_board(game):
    state = game.state
    if game.game == "number":
        title = GAME_EMOJIS["number"] + " <b>Son topish</b>"
        if game.status == "finished":
            if state.get("winner"):
                user = state["winner"]
                return (
                    format(title, "")
                    + "\n"
                    + format(mention(user, state["names"][str(user)]), "")
                    + " topdi! Son: "
                    + format(state["secret"], "")
                    + ". +3 ball."
                )
            reason = "Vaqt tugadi" if state.get("result") == "timeout" else "15 urinish tugadi"
            return f"{title}\n{reason}. Son: {state['secret']}. Ball berilmadi."
        hint = ""
        if state.get("hint"):
            direction = "kattaroq" if state["hint"] == "higher" else "kichikroq"
            hint = f"\nOldingi taxmin {state['last_guess']}; yashirin son {direction}."
        return (
            format(title, "")
            + "\n"
            + format(state["low"], "")
            + "–"
            + format(state["high"], "")
            + " orasidagi butun sonni toping."
            + format(hint, "")
            + "\nUrinish: "
            + format(state["attempts"], "")
            + (
                "/15.\n\nShu xabarga javob qilib faqat son yuboring. Har odam "
                + "urinish orasida 3 soniya kutsin. Xabar yetkazilgach 3 daqiqa; "
                + "topuvchiga +3 ball."
            )
        )
    title = GAME_EMOJIS["math"] + " <b>Tezkor matematika</b>"
    previous = state.get("last_result")
    result = ""
    if previous:
        outcome = (
            mention(previous["winner"], state["names"][str(previous["winner"])]) + " +2 ball"
            if previous["winner"]
            else "Vaqt tugadi"
        )
        result = f"\n{math_expression(previous)} = {previous['answer']}. {outcome}.\n"
    if game.status == "finished":
        scores = sorted(state["scores"].items(), key=lambda pair: (-pair[1], int(pair[0])))
        table = (
            "\n".join(
                (
                    f"{i}. {mention(int(user), state['names'][user])} — {score} ball"
                    for i, (user, score) in enumerate(scores, 1)
                )
            )
            or NO_SCORES
        )
        return f"{title}\n5 savol yakunlandi.{result}\n{table}"
    item = state["questions"][state["round"] - 1]
    return (
        format(title, "")
        + " — "
        + format(state["round"], "")
        + "/5"
        + format(result, "")
        + "\n\n"
        + format(math_expression(item), "")
        + (
            " = ?\n\nTugmani tanlang. Ko‘rsatilgach 20 soniya; har odamga bir "
            + "urinish. Birinchi to‘g‘ri javobga +2 ball."
        )
    )


RPS_ACCEPTED = "O‘yin boshlandi. Yashirin tanlovingizni bosing."
RPS_CHOICE_LOCKED = "Tanlovingiz saqlandi. Uni almashtirib bo‘lmaydi."
RPS_MOVES = {"r": "🪨 Tosh", "s": "✂️ Qaychi", "p": "📄 Qog‘oz"}
RPS_TIMEOUT = "Tosh–qaychi–qog‘oz muddati tugadi. Ball berilmadi. /tqq bilan " + "qayta boshlang."
RPS_LEFT = "Davradosh o‘yindan chiqdi. Tosh–qaychi–qog‘oz bekor qilindi, " + "ball berilmadi."
RPS_RESET = (
    "Bot yoki guruh holati o‘zgardi. Tosh–qaychi–qog‘oz bekor "
    + "qilindi, ball berilmadi. /tqq bilan qayta boshlang."
)


def rps_board(game):
    state = game.state
    title = GAME_EMOJIS["rps"] + " <b>Tosh–qaychi–qog‘oz</b>"

    def name(user):
        return mention(user, state["names"][str(user)])

    if state["phase"] == "lobby":
        target = name(state["target"]) if state.get("target") else "Boshqa bir davradosh"
        return (
            format(title, "")
            + "\n"
            + format(name(game.started_by), "")
            + " o‘yinga chaqirdi.\n"
            + format(target, "")
            + (
                " qabul qilsin.\nKutish: 90 soniya. Bir raund, g‘olibga +2 ball, "
                + "durangda ball yo‘q."
            )
        )
    if game.status == "finished":
        picks = "\n".join(
            f"{name(user)}: {RPS_MOVES[state['choices'][str(user)]]}" for user in state["players"]
        )
        outcome = (
            f"🏆 {name(state['winner'])} yutdi! +2 ball."
            if state.get("winner")
            else "🤝 Durang! Ball berilmadi."
        )
        return f"{title}\n\n{picks}\n\n{outcome}"
    ready = "\n".join(
        f"{name(user)} — " + ("tanladi ✅" if str(user) in state["choices"] else "tanlamoqda…")
        for user in state["players"]
    )
    return (
        format(title, "")
        + "\n\n"
        + format(ready, "")
        + (
            "\n\nQabul qilingandan boshlab 60 soniya. Har kim bir marta "
            + "tanlaydi. Ikkala tanlov tayyor bo‘lgach ochiladi."
        )
    )


QUIZ_START = GAME_EMOJIS["quiz"] + (
    " Viktorina boshlanmoqda! 5 savol, har biriga 30 soniya. To‘g‘ri " + "javob +3, birinchi +2."
)
WYR_START = GAME_EMOJIS["wyr"] + " Qaysi birini tanlaysiz? Ovoz berish uchun 60 soniya."
WYR_FINISHED = "Tanlov yakunlandi. Natijalar so‘rovnomada! ✅"
KROK_START = GAME_EMOJIS["krokodil"] + (
    " Krokodil boshlanmoqda! Boshlovchi so‘zni tugma orqali yashirin " + "ko‘radi."
)
KROK_NEED_PLAYERS = "Krokodil uchun kamida ikki a'zo /qoshilish bilan qo‘shilsin."
KROK_SEE = "So‘zni ko‘rish"
KROK_SKIP = "So‘zni almashtirish"
KROK_HOST_ONLY = "So‘zni faqat hozirgi boshlovchi ko‘ra oladi."
KROK_NO_SKIPS = "Bir turda faqat ikki marta so‘z almashtirish mumkin."
KROK_SKIPPED = "So‘z almashtirilmoqda. So‘zni ko‘rish tugmasini yana bosing."
HYJ_TRUTH = "Haqiqat"
HYJ_DARE = "Jasorat"
HYJ_REFUSE = "Rad etish (−2)"
HYJ_TARGET_ONLY = "Bu tugmani faqat tanlangan davradosh bosa oladi."
HYJ_INVALID_TARGET = "Javob berilgan a'zo /qoshilish bilan o‘yinga qo‘shilgan bo‘lsin."
MAFIA_JOIN = "Mafiaga qo‘shilish (shaxsiy chat)"
MAFIA_JOINED = "Mafiaga qo‘shildingiz! O‘yin boshlanishini guruhda kuting."
MAFIA_LOBBY_CLOSED = "Mafia kutish muddati yopiq, to‘lgan yoki bu havola eskirgan."
MAFIA_ALREADY_PLAYING = (
    "Siz boshqa Mafia o‘yinidasiz. Bir paytda faqat bitta o‘yinda " + "qatnashing."
)
MAFIA_OPT_IN = "Avval o‘sha guruhda /qoshilish yuboring, keyin havolani yana bosing."
MAFIA_TOO_FEW = "Mafia bekor qilindi: kamida 5 ta tayyor davradosh kerak."
MAFIA_DELIVERY_FAILED = (
    "Mafia bekor qilindi: rollarni yetkazib bo‘lmadi. Keyinroq qayta " + "boshlang."
)
MAFIA_RESTART = (
    "Bot qayta ishga tushdi. Kechirasiz, Mafia bekor qilindi. /mafia " + "bilan qayta boshlang."
)
MAFIA_STALE = "Bu Mafia tugmasi eskirgan, siz uchun emas yoki bu bosqichda " + "ishlamaydi."
MAFIA_CHOICE_SAVED = "Tanlovingiz joyida. ✅"
MAFIA_CHECK_AT_DAWN = "Tanlovingiz joyida. ✅ Tekshiruv javobi tongda shaxsiy doskada " + "chiqadi."
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
            format(mention(int(user), state["players"][user]), "")
            + " o‘yindan chiqdi. Roli: <b>"
            + format(MAFIA_ROLE_NAMES[state["roles"][user]], "")
            + "</b>."
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
        "Shaxsiy aloqasi yo‘q yoki chiqib ketganlar ro‘yxatdan olindi: "
        + ", ".join(escape(name[:24]) for name in removed)
        + ".\n"
        if removed
        else ""
    )
    phase = state["phase"]
    if phase in {"lobby", "preparing"}:
        players = "\n".join(
            (
                f"{i}. {mention(int(user), name)}"
                for i, (user, name) in enumerate(state["players"].items(), 1)
            )
        )
        status = (
            "Kutish: 90 soniya. 5–15 kishi. Guruhda /qoshilish yuboring, "
            + "so‘ng havoladan shaxsiy chatga o‘ting."
            if phase == "lobby"
            else "Shaxsiy aloqa va rollar tayyorlanmoqda. Hali tun boshlanmadi."
        )
        mode = (
            "\nKengaytirilgan rejim: 8+ Don, 9+ Ma’shuqa (tinch jamoa), 11+ " + "Manyak (yakka)."
            if state.get("extended_roles")
            else ""
        )
        consent = "\nIsmingiz, ovozingiz va o‘yin oxirida rolingiz guruhda ko‘rsatiladi."
        return (
            format(GAME_EMOJIS["mafia"], "")
            + " <b>Mafia</b> — "
            + format(len(state["players"]), "")
            + "/15\n"
            + format(notice, "")
            + format(status, "")
            + format(mode, "")
            + format(consent, "")
            + "\n\n"
            + format(players, "")
        )
    if phase == "done":
        outcome = MAFIA_OUTCOMES.get(state.get("winner"), "Mafia to‘xtatildi. Ball berilmaydi.")
        roles = "\n".join(
            (
                f"{mention(int(user), state['players'][user])} — {MAFIA_ROLE_NAMES[role]}"
                for user, role in state.get("roles", {}).items()
            )
        )
        return f"{GAME_EMOJIS['mafia']} {outcome}\n{mafia_event(state)}\n\n{roles}"
    status = {
        "night": "🌙 Tun: 60 soniya. Harakatlar shaxsiy chatdagi tugmalarda.",
        "discussion": "☀️ Muhokama: 90 soniya. Guruhda gaplashing.",
        "vote": "🗳 Ovoz berish: 60 soniya. Faqat tirik o‘yinchilar; ovozni "
        + "almashtirish mumkin.",
    }[phase]
    text = (
        format(GAME_EMOJIS["mafia"], "")
        + " Mafia — "
        + format(state["round"], "")
        + "-tur\n"
        + format(mafia_event(state), "")
        + "\n"
        + format(status, "")
        + "\nTirik: "
        + format(len(state["alive"]), "")
        + "."
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
        (
            escape(game.state["players"][who]) + (" (Don)" if value == "don" else "")
            for who, value in proposed.items()
            if value in {"mafia", "don"}
        )
    )
    return (
        format(GAME_EMOJIS["mafia"], "")
        + " Mafia #"
        + format(game.id, "")
        + ". Tayyorlash "
        + format(game.state["setup_attempt"], "")
        + ".\nDastlabki rol: <b>"
        + format(MAFIA_ROLE_NAMES[role], "")
        + "</b>.\n"
        + mafia_role_card(role)
        + (f"Mafia jamoasi: {team}.\n" if role in {"mafia", "don"} else "")
        + (
            "Hali harakat qilmang. Hamma tayyor bo‘lgach rol tasdiqlanadi; "
            + "yangilansa oldingisi bekor."
        )
    )


def mafia_private(game, user):
    from bot.games.mafia.engine import tally

    state, user = (game.state, str(user))
    role = state["roles"][user]
    text = (
        format(GAME_EMOJIS["mafia"], "")
        + " Mafia #"
        + format(game.id, "")
        + " — "
        + format(escape(state.get("chat_title", "")), "")
        + "\nSizning rolingiz: <b>"
        + format(MAFIA_ROLE_NAMES[role], "")
        + "</b>.\n"
        + mafia_role_card(role)
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
                    "Teng ovozda sizning tanlovingiz hal qiladi. Komissarga mafia "
                    + "bo‘lib ko‘rinmaysiz.\n"
                )
            counts = tally(state, mafia=True)
            text += "\n".join(
                (
                    f"{mention(int(who), state['players'][who])}: {count}"
                    for who, count in sorted(counts.items())
                )
            )
        elif role == "doctor":
            text += "Kimni saqlaysiz? O‘zingizni ketma-ket ikki kecha saqlay olmaysiz."
        elif role == "commissioner":
            if "mistress" in state["roles"].values():
                text += (
                    "Bir kishini tekshiring. Tanlovingiz bloklanishi mumkin; javob "
                    + "tongda shu yerda chiqadi."
                )
            else:
                text += "Bir kishini tekshiring. Javob faqat sizga oynachada chiqadi."
        elif role == "mistress":
            text += (
                "Siz tinch jamoada: bir kishining tungi harakatini to‘sing. "
                + "Ketma-ket bir nishon mumkin emas."
            )
        elif role == "manyak":
            text += (
                "Siz yakka o‘ynaysiz. Tunda bir nishonni tanlang; tirik qolib, "
                + "ko‘pi bilan yana bir kishi qolsa yutasiz."
            )
        else:
            text += "Tongni kuting. Sizda tungi harakat yo‘q."
    else:
        text += "Muhokama va kunduzgi ovoz berish guruhda."
    checked = state.get("last_check")
    if role == "commissioner" and checked and (checked["actor"] == user):
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
        f"{GAME_EMOJIS['mafia']} Mafia #{game.id} yakunlandi. "
        + MAFIA_OUTCOMES.get(game.state.get("winner"), "O‘yin bekor qilindi. Ball berilmaydi.")
        + (points_note if game.state.get("winner") else "")
    )


def hyj_choice(game):
    state = game.state
    return (
        format(GAME_EMOJIS["hyj"], "")
        + " "
        + format(mention(state["target"], state["name"]), "")
        + (
            ", haqiqat yoki jasorat?\nTanlash uchun 90 soniya. Faqat siz "
            + "tugmani bosa olasiz. Rad etish: −2 ball."
        )
    )


def hyj_truth(game):
    state = game.state
    return (
        format(GAME_EMOJIS["hyj"], "")
        + " "
        + format(mention(state["target"], state["name"]), "")
        + ", haqiqat:\n"
        + format(escape(state["question"]), "")
        + ("\n\n30 daqiqada matn yoki ovozli xabar bilan javob bering. Javob " + "uchun +5 ball.")
    )


def hyj_dare(game):
    state = game.state
    end = game.phase_deadline_at.astimezone(ZoneInfo(state.get("display_tz", "Asia/Tashkent")))
    return (
        "🎯 "
        + format(mention(state["target"], state["name"]), "")
        + ", jasorat:\n"
        + format(escape(state["prompt"]), "")
        + "\n\nMuddati: "
        + format(end, "%d.%m %H:%M")
        + ". Rad etish: faqat −2, cheklash yoki chiqarish yo‘q."
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
    return f"{GAME_EMOJIS['hyj']} {who} {ending.get(result, 'uchun o‘yin yakunlandi.')}"


def krok_word(word):
    return f"Sizga atalgan so‘z: {word}"


def krok_board(game, final=False):
    state = game.state
    last = state.get("last_result", {})
    lines = []
    if last.get("kind") == "guess":
        guesser = mention(last["guesser"], state["names"].get(str(last["guesser"]), "Davradosh"))
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
            (
                f"{i}. {mention(int(user), state['names'].get(user, 'Davradosh'))} — {score} ball"
                for i, (user, score) in enumerate(scores[:15], 1)
            )
        )
    else:
        host = mention(state["host"], state["names"].get(str(state["host"]), "Davradosh"))
        lines.append(
            format(GAME_EMOJIS["krokodil"], "")
            + " Krokodil "
            + format(state["round"], "")
            + "/10. Boshlovchi: "
            + format(host, "")
            + ".\nTopish uchun 3 daqiqa. Almashtirish qoldi: "
            + format(2 - state["skips"], "")
            + (".\nBoshlovchi so‘zni yozmasdan tushuntirsin, boshqalar guruhga " + "taxmin yozsin.")
        )
    return "\n\n".join(lines)


def duel_lobby(game):
    state = game.state
    starter = mention(game.started_by, state["names"][str(game.started_by)])
    target = (
        mention(state["target"], state["names"][str(state["target"])])
        if state.get("target")
        else "Istalgan davradosh"
    )
    return (
        format(state["emoji"], "")
        + " "
        + format(starter, "")
        + " duelga chaqirdi!\n"
        + format(target, "")
        + " qabul qilsin.\nZar turini boshlovchi tanlaydi. Kutish: 90 soniya."
    )


def duel_rolling(game):
    state = game.state
    first = mention(game.started_by, state["names"][str(game.started_by)])
    second = mention(state["opponent"], state["names"][str(state["opponent"])])
    return (
        format(state["emoji"], "")
        + " Duel, "
        + format(state["round"], "")
        + "-urinish. Teng bo‘lsa qayta tashlayman.\nBirinchi zar: "
        + format(first, "")
        + "\nIkkinchi zar: "
        + format(second, "")
    )


def duel_result(game):
    state = game.state
    winner = mention(state["winner"], state["names"][str(state["winner"])])
    return (
        format(state["emoji"], "")
        + " Natija: "
        + format(state["values"][0], "")
        + " : "
        + format(state["values"][1], "")
        + "\n"
        + format(winner, "")
        + " g‘olib! +2 ball. 🏆"
    )


def quiz_board(game, final=False):
    state = game.state
    heading = (
        "🏆 Viktorina yakunlandi!"
        if final
        else f"{GAME_EMOJIS['quiz']} Viktorina: {state.get('question_index', 0) + 1}/5"
    )
    scores = sorted(state.get("scores", {}).items(), key=lambda pair: (-pair[1], int(pair[0])))
    rows = [
        f"{i}. {mention(int(user), state['names'].get(user, 'Davradosh'))} — {score} ball"
        for i, (user, score) in enumerate(scores[:15], 1)
    ]
    return heading + "\n" + ("\n".join(rows) if rows else "Hali to‘g‘ri javob yo‘q.")


QUIET_ASSIGN = "Hozir tinch vaqt. Vazifani tinch vaqt tugagach bering."
PENDING_CHALLENGE = "Bu guruhda hali bajarilmagan vazifa bor. Avval u yakunlansin."
NO_CHALLENGE_CANDIDATE = "Mos davradosh yoki vazifa topilmadi. /qoshilish bilan qo‘shiling."
CHALLENGE_SEND_FAILED = "Vazifani yuborib bo‘lmadi. Birpasdan so‘ng yana urinib ko‘ring."
CHALLENGE_ARGUMENTS = "Masalan: /vazifa video, /vazifa ovoz, /vazifa surat yoki /vazifa" + " matn."
NO_SCORES = "Ilk ball hali oldinda. Davrani boshlaymizmi?"


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
        format(mention(user_id, "Do‘stimiz"), "")
        + ", vazifa muddati tugadi. "
        + format(penalty, "")
        + " Keyingi safar albatta!"
    )


def debtors_suffix(debtors) -> str:
    if not debtors:
        return ""
    names = ", ".join((mention(user_id, name) for user_id, name in debtors))
    return f"\n\n🙂 Vazifasi qolgan do‘stlarimiz: {names}. Keyingi safar birga bajaramiz!"


def my_stats(name: str, total: int, done: int, missed: int) -> str:
    return (
        format(escape(name), "")
        + "\n⭐ Jami: "
        + format(total, "")
        + " ball\n✅ Bajarilgan vazifalar: "
        + format(done, "")
        + "\n⌛ O‘tkazilgan: "
        + format(missed, "")
    )


def leaderboard(weekly, overall) -> str:

    def rows(items):
        return (
            "\n".join(
                (
                    f"{i}. {mention(user_id, name)} — {points} ball"
                    for i, (user_id, name, points) in enumerate(items, 1)
                )
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
    "tz": "Vaqt mintaqasini kiriting, masalan: Asia/Tashkent. Shu xabarga " + "javob yozing.",
    "daily_time": "Kunlik xabar vaqtini HH:MM shaklida kiriting (09:00). Shu "
    + "xabarga javob yozing.",
    "quiet_start": "Tinch vaqt boshlanishini HH:MM shaklida kiriting. Shu xabarga "
    + "javob yozing.",
    "quiet_end": "Tinch vaqt tugashini HH:MM shaklida kiriting. Shu xabarga javob " + "yozing.",
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
        '<a href="tg://user?id='
        + format(user.id, "")
        + '">'
        + format(escape(user.first_name), "")
        + "</a>, "
        + format(SETTING_PROMPTS[field], "")
    )


def group_help(instagram_handle=None) -> str:
    commands = "\n".join(
        (f"/{command} — {description}" for command, description in GROUP_COMMANDS.items())
    )
    details = (
        "\n\n🎯 Vazifalar: faqat /qoshilish bilan rozilik berganlar "
        + "orasidan. /chiqish istalgan payt ishlaydi.\n"
        + GAME_EMOJIS["duel"]
        + " /duel ni javob tarzida yoki ochiq yuboring; zarni bot tashlaydi.\n"
        + GAME_EMOJIS["rps"]
        + " /tqq — tosh–qaychi–qog‘oz; yashirin tanlov, g‘olibga +2 ball.\n"
        + GAME_EMOJIS["number"]
        + " /sontop — yashirin son; "
        + GAME_EMOJIS["math"]
        + " /matematika — 5 tezkor savol. /oyinlar — ro‘yxat.\n"
        + GAME_EMOJIS["quiz"]
        + " /viktorina: 5 savol, har biriga 30 soniya.\n"
        + GAME_EMOJIS["wyr"]
        + " /tanla: bir daqiqalik ochiq tanlov.\n"
        + GAME_EMOJIS["krokodil"]
        + " /krokodil: yashirin so‘z, 10 tur, har biri 3 daqiqa.\n"
        + GAME_EMOJIS["hyj"]
        + " /hyj: haqiqatga 30 daqiqa, jasoratga 1 soat; rad etish −2.\n"
        + GAME_EMOJIS["mafia"]
        + (
            " /mafia: 5–15 kishi, 90 soniyalik havola orqali qo‘shilish. "
            + "Hamma botni shaxsiy chatda ochishi kerak.\n"
        )
        + GAME_EMOJIS["secret"]
        + (
            " /yashirin: 3–20 kishi, 2/6/24 soatlik fon o‘yini; /fosh ni "
            + "javob bilan ishlating.\n"
        )
        + GAME_EMOJIS["kim"]
        + " /kimaytdi: 4–12 kishi, shaxsiy matn, 30 soniyalik anonim taxmin.\n"
        + GAME_EMOJIS["telephone"]
        + " /telefon: 4–10 kishi, 2 daqiqalik navbat, ovoz <=30 soniya.\n"
        + GAME_EMOJIS["memory"]
        + (
            " /eslaysizmi: 3–10 kishi, bitta surat, izoh taxmindan keyin "
            + "ochiladi.\nShaxsiy havoladan rozilik bilan kiring; Mafia bilan "
            + "birga bir odamga bitta faol shaxsiy o‘yin. Admin yashirgan "
            + "material uchun muallif ball olmaydi. Media uchun botning "
            + "o‘chirish huquqi kerak.\n🛑 /stop: boshlovchi yoki admin. Duel "
            + "yoki fon o‘yinini tanlash uchun doskasiga javob bering.\n⏰ Kunlik"
            + " xabar 0–15 daqiqaga tarqatiladi; haftalik xulosa yakshanba "
            + "20:00–21:00. Tinch vaqtda avtomatik xabar/vazifalar kutiladi."
        )
    )
    footer = f"\n\nMuallif: @{escape(instagram_handle)}" if instagram_handle else ""
    return f"<b>{SLOGAN}!</b>\n\n" + commands + details + footer


def daily_post(template: str, group: str) -> str:
    return escape(template).replace("{group}", escape(group))


def start_text(first_name: str, instagram_handle: str) -> str:
    return (
        "Salom, "
        + format(escape(first_name), "")
        + "! 👋\n\n<b>"
        + format(SLOGAN, "")
        + (
            "</b>\nMen Oqibat — davrangizning boshlovchisiman. Do‘stlarni "
            + "birga yig‘amiz!\nVazifa, viktorina, duel — birga sinab ko‘ramiz!"
            + "\n\nYordam: /help\n\nMuallif: @"
        )
        + format(escape(instagram_handle), "")
    )


def help_text(instagram_handle: str) -> str:
    return (
        "/start — bot bilan tanishish\n/help — yordam\n\n/maxfiylik — "
        + "ma’lumotlar haqida\n/malumotlarimni_ochir — shaxsiy chatda "
        + "o‘chirish\n/stats — faqat bot egasi uchun\n\nBotni guruhga admin "
        + "qilib qo‘shing. Guruh buyruqlari:\n\n"
        + group_help(instagram_handle)
    )


def weekly_summary(week, data, instagram_handle, *, compact=False):

    def name(value):
        return value[:24] + "…" if compact and len(value) > 24 else value

    title = f"🏆 <b>Haftalik oqibat</b> — {week:%d.%m.%Y} haftasi\n{SLOGAN}!"
    top = (
        "\n".join(
            (
                f"{i}. {mention(user, name(label))} — {points} ball"
                for i, (user, label, points) in enumerate(data["top"], 1)
            )
        )
        or NO_SCORES
    )
    active = data["active"]
    activity = (
        "🔥 Eng faol: "
        + format(mention(active[0], name(active[1])), "")
        + " — "
        + format(active[2], "")
        + " ta muvaffaqiyatli ishtirok."
        if active
        else "🔥 Bu haftada hali ball olgan ishtirok yo‘q."
    )
    return (
        format(title, "")
        + "\n\n"
        + format(top, "")
        + "\n\n"
        + format(activity, "")
        + "\n🎯 Hafta vazifalari: bajarildi "
        + format(data["done"], "")
        + ", o‘tkazildi "
        + format(data["missed"], "")
        + ". Hozir kutilmoqda: "
        + format(data["pending"], "")
        + ".\n\nMuallif: @"
        + format(escape(instagram_handle), "")
    )


OWNER_STATS_DESCRIPTION = "Bot egasi uchun holat"
WEBHOOK_INFO_FAILED = "Webhook holati olinmadi. Token, internet va sozlamalarni tekshiring."


def webhook_info_status(matches, pending, last_error):
    match = "mos" if matches else "mos emas"
    at = last_error.astimezone(ZoneInfo("UTC")).isoformat() if last_error else "yo‘q"
    return (
        "getWebhookInfo: URL sozlangan rejimga "
        + format(match, "")
        + ".\nKutayotgan yangilanishlar: "
        + format(pending, "")
        + ".\nOxirgi qayd etilgan xato vaqti (UTC): "
        + format(at, "")
        + "."
    )


def owner_error_alert(summary, count):
    at = summary["at"].astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S UTC")
    chat = str(summary["chat_id"]) if summary["chat_id"] is not None else "—"
    return (
        "⚠️ <b>Bot xatosi</b>\nTur: "
        + format(escape(summary["type"]), "")
        + "\nJoy: "
        + format(escape(summary["where"]), "")
        + "\nChat: "
        + format(chat, "")
        + "\nVaqt: "
        + format(at, "")
        + "\nHodisalar: "
        + format(count, "")
        + "\nBirlashtirilgan qo‘shimcha xatolar: "
        + format(count - 1, "")
        + ("\nTafsilot uchun server jurnalini tekshiring; xabar matni bu " + "yerga yuborilmaydi.")
    )


PRIVACY_DESCRIPTION = "Ma’lumotlar maxfiyligi"
ERASE_DESCRIPTION = "Ma’lumotlarimni o‘chirish"
PRIVACY = (
    "🔐 <b>Maxfiylik</b>\nTelegram ID, ism va username; guruh "
    + "sozlamalari, qo‘shilish roziligi, oxirgi faollik, vazifa/o‘yin "
    + "natijalari va ballar saqlanadi. Ular o‘yinlar, reyting va "
    + "vazifalar uchun kerak. Oddiy yozishmalar, surat, ovoz yoki video"
    + " fayllari saqlanmaydi. O‘yin holati tanlangan javoblar va "
    + "ismlarni, rozilik bilan yuborgan o‘yin javobingizni hamda "
    + "ovoz/suratning Telegram file_id sini saqlashi mumkin; muallifni "
    + "ochish, ovozni qayta yuborish va admin yashirishi uchun kerak. "
    + "Media faylini yuklab olib saqlamaymiz.\nRozilikdan /chiqish bilan"
    + " chiqing. Shaxsiy chatda /malumotlarimni_ochir orqali "
    + "ma’lumotlaringizni tasdiqlab o‘chiring. Avval yuborilgan "
    + "Telegram xabarlari va operatorning tashqi zaxira nusxalari bu "
    + "buyruq bilan o‘chmaydi."
)
OWNER_ONLY = "Bu buyruq faqat bot egasi uchun."
ERASE_CONFIRM = "Ha, ma’lumotlarimni o‘chiring"
ERASED_NAME = "O‘chirilgan davradosh"
ERASE_WARNING = (
    "Ballar, vazifalar, guruhlardagi qatnashish va o‘yinlardagi "
    + "shaxsiy izlaringiz o‘chadi. Bog‘liq faol o‘yinlar tugaydi; "
    + "umumiy o‘yin yozuvlari shaxssizlanadi. Qaytarib bo‘lmaydi. Tugma"
    + " 5 daqiqa amal qiladi. Telegramdagi eski xabarlar va tashqi "
    + "zaxiralar alohida boshqariladi. Tasdiqlaysizmi?"
)
ERASE_WORKING = "So‘rov tekshirilmoqda."
ERASE_EXPIRED = "Tasdiq eskirgan yoki sizga tegishli emas. Buyruqni qayta yuboring."
ERASE_DONE = "Ma’lumotlaringiz o‘chirildi. Qayta foydalanish uchun /start yuboring."


def owner_stats(data):
    games = (
        "\n".join(
            (
                f"{escape(PRIVATE_GAME_NAMES.get(kind, kind))}: {count}"
                for kind, count in sorted(data["games"].items())
            )
        )
        or NO_SCORES
    )
    return (
        "📊 <b>Bot holati</b>\nFaol guruhlar: "
        + format(data["groups"], "")
        + "\nRozilik bergan a’zolar: "
        + format(data["opted"], "")
        + "\nOxirgi 24 soatda faol: "
        + format(data["active"], "")
        + "\n7 kunda boshlangan o‘yinlar:\n"
        + format(games, "")
        + "\nYuborish navbati: "
        + format(data["queue"], "")
        + "\nOxirgi tekshiruv: "
        + format(data["tick"] * 1000, ".1f")
        + " ms"
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
            (
                f"{index}. {mention(user, name[:32])} — {points} ball"
                for index, (user, name, points) in enumerate(rows[:5], 1)
            )
        )
        or NO_SCORES
    )
    return f"🏆 <b>{SEASON_TITLE}</b> — {season_month(day)}\n{winners}"


def achievement_list(rows):
    unlocked = {row.key for row in rows}
    return "🏅 <b>Yutuqlarim</b>\n" + "\n".join(
        (("✅ " if key in unlocked else "🔒 ") + label for key, label in ACHIEVEMENTS.items())
    )


def achievement_batch(items):
    grouped = {}
    for user, name, key in items:
        if key in ACHIEVEMENTS:
            grouped.setdefault((user, name), []).append(ACHIEVEMENTS[key])
    return "🏅 <b>Yangi yutuqlar!</b>\n" + "\n".join(
        (
            f"{mention(user, name[:32])}: {', '.join(labels)}"
            for (user, name), labels in grouped.items()
        )
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
    if game.game in {"quiz", "krokodil", "math"}:
        scores = sorted(state.get("scores", {}).items(), key=lambda pair: (-pair[1], int(pair[0])))
        rows = [
            (state.get("names", {}).get(user, "Davradosh"), score)
            for user, score in scores[:5]
            if score > 0
        ]
    elif game.game in {"duel", "rps"} and state.get("winner"):
        rows = [(state["names"].get(str(state["winner"]), "Davradosh"), 2)]
    elif game.game == "number" and state.get("winner"):
        rows = [(state["names"][str(state["winner"])], 3)]
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


PRIVATE_GAME_BUSY = (
    "Siz boshqa shaxsiy o‘yinda qatnashyapsiz. Avval o‘sha o‘yin " + "tugashini kuting."
)
PRIVATE_GAME_CLOSED = (
    "Bu lobby yopilgan yoki o‘yin topilmadi. Guruhdagi yangi " + "havoladan qo‘shiling."
)
PRIVATE_GAME_JOINED = "Roziligingiz qabul qilindi. Lobby tugagach topshiriq shu yerga " + "keladi."
PRIVATE_GAME_INPUT_WAIT = "Hozir shaxsiy javob qabul qilmayman. O‘yin ko‘rsatmasini kuting."
PRIVATE_GAME_INVALID = (
    "Havola, @eslatma va uzatilgan xabar qabul qilmayman. "
    + "Ko‘rsatmadagi tur va uzunlikda yangi javob yuboring."
)
PRIVATE_GAME_SAVED = "Javobingiz joyida! Yana yuborish shart emas. ✅"
PRIVATE_GAME_ENDED = (
    "Shaxsiy o‘yin tugadi yoki bekor qilindi. Endi boshqa o‘yinga " + "qo‘shilishingiz mumkin."
)
PRIVATE_GAME_NOT_ENOUGH = (
    "Davradoshlar yoki bankdagi turli so‘zlar yetarli emas. O‘yin " + "bekor qilindi."
)
PRIVATE_GAME_MAFIA_INPUT = "Mafia harakatini shu o‘yinning shaxsiy tugmalari orqali tanlang."
PRIVATE_GAME_HIDE = "🙈 Admin: yashirish"
PRIVATE_GAME_HIDE_WAIT = (
    "Admin huquqi va material tekshirilmoqda. Natija shaxsiy xabarda " + "keladi."
)
PRIVATE_GAME_HIDDEN = "Admin tomonidan yashirildi"
PRIVATE_GAME_HIDE_DENIED = "Bu tugma faqat guruh adminlari uchun."
PRIVATE_GAME_HIDE_DONE = "Yashirildi; muallifning shu material uchun bali bekor qilindi."
PRIVATE_GAME_HIDE_FAILED = (
    "Material bali bekor qilindi, lekin Telegramda yashirish "
    + "bajarilmadi. Admin xabarni qo‘lda o‘chirsin va bot logini "
    + "tekshirsin."
)
PRIVATE_GAME_HIDE_MEDIA = (
    "Bali bekor qilindi, izoh belgilandi. Media o‘chmadi: o‘chirish "
    + "huquqini bering yoki admin o‘chirsin."
)
SECRET_DURATION = "Davomiylik: {hours} soat"
SECRET_REVEAL = GAME_EMOJIS["secret"] + " {hunter} {target}ni topdi: <b>{word}</b>. +10 ball!"
SECRET_EXPOSED = "🔎 {accuser} ovchini fosh qildi: {hunter}. So‘z: <b>{word}</b>. " + "+5 ball!"
SECRET_WRONG = "Gumon noto‘g‘ri: −2 ball. Keyingi gumon bir soatdan keyin."
SECRET_ACCUSE_LIMIT = (
    "Gumon uchun /fosh ni gumon qilgan odamingizning xabariga javoban"
    + " yuboring. O‘zingiz o‘yinchi bo‘lishingiz kerak; jami 3 gumon va"
    + " xato gumondan keyin 1 soat kutish bor."
)
SECRET_WORD_DM = GAME_EMOJIS["secret"] + (
    " Nishoningiz: {target}. Maxfiy so‘z: <b>{word}</b>. Uni o‘zingiz"
    + " oshkor qilmang. Nishon guruhda aytsa +10 (ko‘pi bilan 3 marta)."
)
SECRET_NO_MORE = "Uchta muvaffaqiyatga erishdingiz. Endi yangi so‘z berilmaydi."
PRIVATE_GAME_NAMES = {
    "secret": "Yashirin topshiriq",
    "kim": "Kim aytdi?",
    "telephone": "Ovozli buzilgan telefon",
    "memory": "Eslaysizmi?",
}
MEMORY_PROMPT = GAME_EMOJIS["memory"] + (
    " Bitta yangi surat yuboring. Ixtiyoriy izoh: qachon/qayerda "
    + "(<=300 belgi). Havola, @eslatma, uzatilgan rasm yoki hujjat "
    + "qabul qilmayman. Tayyorlashdan so‘ng 5 daqiqa bor. Surat guruhga"
    + " spoiler bilan chiqadi; taxmindan keyin ismingiz va izoh "
    + "ochiladi."
)
PRIVATE_GAME_NEED_DELETE = (
    "Bu media o‘yini uchun botga xabarlarni o‘chirish huquqini "
    + "bering. Huquq keyin yo‘qolsa, yashirish belgisi media faylini "
    + "olib tashlamaydi; admin o‘chirsin."
)
PRIVATE_GAME_DELIVERY_FAILED = (
    "O‘yin xabarini yetkazib bo‘lmadi. Bot huquqlari, tarmoq va logni"
    + " tekshiring. O‘yin bekor qilindi."
)
TELEPHONE_FIRST = GAME_EMOJIS["telephone"] + (
    " Asl jumla: <b>{phrase}</b>\nIkki daqiqada uni ovozli xabar qilib"
    + " ayting (ko‘pi bilan 30 soniya). Ovozlar o‘yin oxirida guruhda "
    + "ochiladi."
)
TELEPHONE_REPEAT = GAME_EMOJIS["telephone"] + (
    " Faqat shu ovozni eshitib, ikki daqiqada o‘z ovozingizda "
    + "takrorlang (ko‘pi bilan 30 soniya)."
)
TELEPHONE_LAST = GAME_EMOJIS["telephone"] + (
    " Siz oxirgi odamsiz. Faqat shu ovozni eshitib, ikki daqiqada "
    + "eshitganingizni matn qilib yozing (1–300 belgi, havola va "
    + "@eslatmasiz)."
)
TELEPHONE_ORIGINAL = GAME_EMOJIS["telephone"] + " Asl jumla: <b>{phrase}</b>"
TELEPHONE_MISSING = "Yakuniy matn kelmadi. Kelgan ovozlar ketma-ket ochiladi."
KIM_QUESTION = GAME_EMOJIS["kim"] + (
    " Kim aytdi? Savol: <b>{question}</b>\nBir yangi matnli javob "
    + "yuboring (1–300 belgi, havola va @eslatmasiz). Tayyorlashdan "
    + "so‘ng 5 daqiqa bor. Javob anonim guruhga chiqadi, taxmindan "
    + "keyin muallif ochiladi."
)
PRIVATE_GAME_NO_ANSWERS = "Javoblar kelmadi, bu davrani yopdik. Yana boshlash mumkin!"
PRIVATE_GUESS_DENIED = (
    "Faqat o‘yinchi taxmin qiladi; yuboruvchi o‘z materialiga ovoz " + "bera olmaydi."
)
PRIVATE_GUESS_SAVED = "Taxmin saqlandi. Natija raund oxirida ochiladi."


def private_game_board(game):
    state = game.state
    title = PRIVATE_GAME_NAMES[game.game]
    names = ", ".join(escape(name) for name in state.get("players", {}).values()) or "—"
    if state["phase"] == "lobby":
        if game.game == "memory":
            return (
                GAME_EMOJIS["memory"]
                + (
                    " <b>Eslaysizmi?</b> · lobby 5 daqiqa, 3–10 kishi\nBitta suratni "
                    + "shaxsiy yuborasiz. Guruhga spoiler bilan chiqadi; 30 soniya "
                    + "taxmindan keyin ismingiz va ixtiyoriy izohingiz ochiladi. Faqat "
                    + "shaxsiy havoladan rozilik bilan qo‘shiling.\n"
                )
                + names
            )
        if game.game == "telephone":
            return (
                GAME_EMOJIS["telephone"]
                + (
                    " <b>Ovozli buzilgan telefon</b> · lobby 3 daqiqa, 4–10 kishi\n"
                    + "Navbatda shaxsiy ovozni takrorlaysiz; oxirgi odam matn yozadi. "
                    + "Asl jumla, yakuniy matn va ovozlar ismlar bilan guruhga "
                    + "chiqariladi. Faqat shaxsiy havoladan rozilik bilan qo‘shiling.\n"
                )
                + names
            )
        if game.game == "kim":
            return (
                GAME_EMOJIS["kim"]
                + (
                    " <b>Kim aytdi?</b> · lobby 3 daqiqa, 4–12 kishi\nSavol shaxsiy "
                    + "keladi. Matnli javobingiz guruhga avval anonim, 30 soniyalik "
                    + "taxmindan keyin ismingiz bilan chiqadi.\nFaqat shaxsiy havolani "
                    + "bosib rozilik bilan qo‘shiling.\n"
                )
                + names
            )
        consent = (
            "Nishon va so‘z shaxsiy keladi. Yutuq yoki fosh bo‘lsa, ismingiz "
            + "va so‘z guruhga chiqariladi."
        )
        return (
            format(GAME_EMOJIS["secret"], "")
            + " <b>"
            + format(title, "")
            + "</b> · lobby 5 daqiqa, 3–20 kishi\n"
            + format(consent, "")
            + (
                "\nFaqat pastdagi shaxsiy havola orqali rozilik bilan qo‘shiling.\n"
                + "Davomiylik: "
            )
            + format(state["hours"], "")
            + " soat\n"
            + format(names, "")
        )
    scores = state.get("scores", {})
    table = "\n".join(
        (
            f"{escape(name)}: {scores.get(user, 0)} ball"
            for user, name in state.get("players", {}).items()
        )
    )
    icon = {
        "secret": GAME_EMOJIS["secret"],
        "kim": GAME_EMOJIS["kim"],
        "telephone": GAME_EMOJIS["telephone"],
        "memory": GAME_EMOJIS["memory"],
    }[game.game]
    return (
        format(icon, "")
        + " <b>"
        + format(title, "")
        + "</b> · "
        + format("tugadi" if game.status == "finished" else "davom etmoqda", "")
        + "\n"
        + format(table, "")
    )


def private_guess_name(index, name):
    return f"{index}. {name}"


def private_answer(game, reveal=False):
    state = game.state
    item = state["items"][state["item"]]
    if game.game == "memory":
        text = f"{GAME_EMOJIS['memory']} {state['round']}/{len(state['order'])}"
        if reveal:
            author = escape(state["players"][str(item["user_id"])])
            caption = escape(item.get("caption", ""))
            return text + f"\nYuboruvchi: <b>{author}</b>\n{caption}"
        return text + "\nKim yuborgan? 30 soniyada bitta taxmin tanlang. Izoh keyin ochiladi."
    text = f"{GAME_EMOJIS['kim']} {state['round']}/{len(state['order'])}\n{escape(item['text'])}"
    if reveal:
        author = escape(state["players"][str(item["user_id"])])
        return text + f"\n\nMuallif: <b>{author}</b>. Raund yakunlandi."
    return text + "\n\nKim yozgan? 30 soniyada bitta taxmin tanlang."


def telephone_item(game, item_id):
    item = game.state["items"][item_id]
    name = escape(game.state["players"][item_id])
    if item["kind"] == "text":
        return f"📝 Yakuniy matn — {name}:\n{escape(item['text'])}"
    return f"🎙 {item['turn'] + 1}. {name}"
