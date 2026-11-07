# Oqibat Bot: 0–9-bosqichlarni Telegramda tekshirish

Bu ro‘yxat Sardorbek va yana ikki kishi uchun. **A** — Sardorbek, guruh egasi va
administrator; **B** va **C** — oddiy a'zolar. Guruhda uch kishi va bot bo‘ladi.
Har bir qadamni bajargach, natija to‘g‘ri bo‘lsa `[ ]` ni `[x]` qiling. Bajarmagan
qadamni belgilamang; sababini yoniga yozing. Shartli qadam mos kelmasa `Mos emas`
deb yozing. Uzoq kutiladigan sinovlarni keyinroq tugatish mumkin.

0–6-bosqichlar uchun uch kishi yetadi. 13-bo‘limdagi Mafia uchun kamida besh kishi
kerak. Haftalik xulosa 14-bo‘limda, rasmli natijalar va server 15-bo‘limda.

## 1. BotFather, Python va .env

- [ ] **1.1.** Telegramdagi [@BotFather](https://t.me/BotFather) ga `/newbot` yuboring.
  Botga ism va oxiri `bot` bilan tugaydigan bo‘sh username tanlang.
  **Kutiladi:** BotFather bot havolasi va token beradi. Tokenni faqat o‘z `.env`
  faylingizga yozing. Token parol kabi maxfiy.
- [ ] **1.2.** PowerShellni oching va loyiha papkasiga o‘ting:

  ```powershell
  Set-Location 'D:\Coding projects\oqibat bot'
  py -3.12 -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  ```

  **Kutiladi:** Python 3.12 muhiti va kutubxonalar o‘rnatiladi. Bu qo‘llanmada
  `.venv` ichidagi dasturlar to‘liq yo‘li bilan chaqiriladi; muhitni yoqish shart emas.
- [ ] **1.3.** `.env` hali yo‘q bo‘lsa nusxa oling; mavjud bo‘lsa uni oching:

  ```powershell
  if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
  notepad .env
  ```

  **Kutiladi:** o‘z tokeningiz `BOT_TOKEN` ga, botning username qiymati `BOT_USERNAME`
  ga yoziladi. `BOT_USERNAME` — ko‘rinadigan ism yoki `https://t.me/...` havola emas.
  `INSTAGRAM_HANDLE` ga Instagram nomingizni yozing. Quyidagilarni mahalliy sinovda qoldiring:

  ```dotenv
  DATABASE_URL=sqlite+aiosqlite:///./oqibat.db
  ENVIRONMENT=development
  LOG_LEVEL=INFO
  USE_WEBHOOK=false
  DB_POOL_SIZE=15
  ```

  `OWNER_ID` — A ning raqamli Telegram ID qiymati; telefon raqami yoki `@username`
  emas. Uni bilsangiz yozing. Bilmasangiz, faqat keyingi qadam uchun vaqtincha `1`
  yozib turing; botni guruhda ishlatishdan oldin haqiqiy ID bilan almashtirasiz.
- [ ] **1.4.** Faqat `OWNER_ID` noma'lum bo‘lsa: botning boshqa nusxalari to‘xtagan
  va webhook ishlamayotgan bo‘lsin. A yangi botning shaxsiy chatiga `/start` yuborsin.
  Botni hali ishga tushirmasdan, shu PowerShellga quyidagini nusxalang:

  ```powershell
  @'
  import asyncio
  from aiogram import Bot
  from aiogram.exceptions import TelegramConflictError
  from bot.config import Settings

  async def main():
      async with Bot(Settings().bot_token.get_secret_value()) as bot:
          updates = await bot.get_updates(timeout=1, request_timeout=10)
          for update in updates:
              message = update.message
              if message and message.chat.type == "private" and message.from_user:
                  print("OWNER_ID=" + str(message.from_user.id))

  try:
      asyncio.run(main())
  except TelegramConflictError:
      print("Conflict: boshqa bot nusxasi yoki webhookni to'xtating.")
  except Exception:
      print("ID olinmadi. Sozlama va internetni scripts/check_env.py bilan tekshiring.")
  '@ | .\.venv\Scripts\python.exe -
  ```

  **Kutiladi:** A ning yaqinda yuborgan shaxsiy xabari uchun `OWNER_ID=...` chiqadi;
  token ekranga chiqmaydi. Shu raqamni `.env` ga saqlang. Bo‘sh natija chiqsa,
  A yana `/start` yuborsin va takrorlang. `Conflict` chiqsa, boshqa bot nusxasi yoki
  webhookni to‘xtating. Haqiqiy ID allaqachon ma'lum bo‘lsa bu qadam `Mos emas`.
- [ ] **1.5.** Bazani tayyorlang, keyin sozlamalarni tekshiring:

  ```powershell
  .\.venv\Scripts\alembic.exe upgrade head
  .\.venv\Scripts\python.exe scripts\check_env.py
  $LASTEXITCODE
  .\.venv\Scripts\python.exe -m bot --check
  ```

  **Kutiladi:** tekshiruvchi token shakli, haqiqiy Telegram `getMe` javobi, bot nomi,
  baza aloqasi va jadvallar uchun `[OK]` chiqaradi; uning chiqish kodi `0` bo‘ladi.
  `[X]` chiqsa, o‘sha satrdagi ko‘rsatmani bajaring. `--check` esa faqat sozlama va
  jadvallarni tekshiradi; Telegram tokenini tasdiqlamaydi. PowerShellda oldin berilgan
  muhit qiymatlari `.env` dan ustun turadi; nom kutilmaganda boshqacha bo‘lsa yangi
  PowerShell oynasida loyiha papkasidan tekshiring.
- [ ] **1.6.** Botni jurnal bilan ishga tushiring:

  ```powershell
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
  $env:PYTHONIOENCODING = 'utf-8'
  .\.venv\Scripts\python.exe -u -m bot 2>&1 | Tee-Object -FilePath .\bot-live.log -Append
  ```

  **Kutiladi:** `Starting long polling` chiqadi, oyna ishlab turadi. Faqat bitta bot
  nusxasini ishlating. To‘xtatish uchun shu oynada **Ctrl+C** bosing. Keyingi
  kompyuter buyruqlari uchun ikkinchi PowerShell oynasini loyiha papkasida oching.

## 2. Shaxsiy chat va uch kishilik guruh — 0 va 1-bosqich

- [ ] **2.1.** A, B va C botning shaxsiy chatida `/start` yuborsin.
  **Kutiladi:** o‘zbekcha salom, “Guruhda oqibat bo‘lsin”, `Muallif: @...` va
  “Botni guruhingizga qo‘shing” tugmasi ko‘rinadi.
- [ ] **2.2.** Shaxsiy chatda `/help` yuboring va guruhga qo‘shish tugmasini bosing.
  **Kutiladi:** o‘zbekcha yordam va muallif bor; tugma Telegramning guruh tanlash
  oynasini ochadi.
- [ ] **2.3.** A uch kishilik alohida **sinov guruhini** ochsin. Botni avval oddiy
  a'zo qilib qo‘shing. **Kutiladi:** bot uni administrator qilishni so‘raydi;
  hali odatdagi vazifa/o‘yinlar ishga tushmaydi.
- [ ] **2.4.** A botni administrator qilsin, a'zolarni cheklash, xabarlarni o‘chirish
  va qadash huquqlarini bersin. **Kutiladi:** salomlashuv va “O‘yinga qo‘shilish”
  tugmasi chiqadi. Administrator bot oddiy guruh xabarlarini oladi; bu sinov uchun
  BotFatherdagi privacy rejimini alohida o‘zgartirish talab qilinmaydi.
- [ ] **2.5.** A, B, C qo‘shilish tugmasini bossin. B uni yana bossin.
  **Kutiladi:** har biriga shaxsiy tasdiq oynachasi chiqadi; B ikkinchi ishtirokchi
  sifatida yana qo‘shilib qolmaydi.
- [ ] **2.6.** B `/chiqish`, keyin `/qoshilish` yuborsin.
  **Kutiladi:** chiqish va qayta qo‘shilish tasdiqlanadi. A'zo faqat rozilik bergach
  tasodifiy vazifa/o‘yin tanloviga kiradi.
- [ ] **2.7.** B guruhdan chiqib qayta kirsin. Keyin `/qoshilish` yuborsin.
  **Kutiladi:** kirishning o‘zi avvalgi rozilikni tiklamaydi; qayta qo‘shilish ishlaydi.
- [ ] **2.8.** Faol vazifa/o‘yin yo‘q paytda A botni olib tashlab, yana admin qilib qo‘shsin.
  **Kutiladi:** bot qayta salomlashadi va ishlashda davom etadi; oldingi ball/sozlamalar
  saqlanadi. Bot yo‘qligida unga topshiriq yuborilishi kutilmaydi.
- [ ] **2.9.** Guruhda `/help` va buyruqlar menyusini oching.
  **Kutiladi:** hozir ishlaydigan buyruqlar, jumladan `/duel`, `/viktorina`, `/tanla`,
  `/krokodil`, `/hyj`, `/stop` bor. `/mafia` hali ro‘yxatda yo‘q.

## 3. Administrator sozlamalari

Vaqt/son yozishda botning **aynan savol xabariga javob bering**.

- [ ] **3.1.** A `/sozlamalar` yuborsin, B menyudagi tugmani bossin.
  **Kutiladi:** B ga admin emasligi aytiladi, qiymat o‘zgarmaydi.
- [ ] **3.2.** A “Vaqt mintaqasi”ni `Asia/Tashkent` qilsin, keyin `Xato/Mintaqa` ni sinasin.
  **Kutiladi:** haqiqiy mintaqa saqlanadi, noto‘g‘risi rad etiladi.
- [ ] **3.3.** “Kunlik xabar”ni o‘chirib/yoqing va vaqtini `22:15` qilib yozing.
  **Kutiladi:** ikkala o‘zgarish menyuda saqlanadi; `25:90` rad etiladi.
- [ ] **3.4.** Kuniga vazifalar sonini navbat bilan `0`, `1`, `2`, `3` qiling.
  **Kutiladi:** har biri saqlanadi. `0` avtomatik vazifalarni o‘chiradi; adminning
  qo‘lda `/vazifa` yuborishi tinch vaqt tashqarisida ishlayveradi.
- [ ] **3.5.** Vazifa muddatini `2`, `6`, `10`, `24` soat qilib ko‘ring.
  **Kutiladi:** tanlangan qiymat saqlanadi; yangi vazifa shu muddat bilan yaratiladi.
  Oldin berilgan vazifaning muddati qayta yozilmaydi.
- [ ] **3.6.** Jazo turini `off`, `points`, `mute`, `kick` qilib ko‘ring; keyin `points` qoldiring.
  **Kutiladi:** har bir tur saqlanadi; ularning haqiqiy ta'siri 6-bo‘limda tekshiriladi.
- [ ] **3.7.** Cheklash muddatini `1`, `3`, `7` kun qilib ko‘ring.
  **Kutiladi:** har bir tanlov saqlanadi.
- [ ] **3.8.** “Nechta o‘tkazishdan keyin chiqarish”ga `2`, keyin `0` va `101` yozing.
  **Kutiladi:** `2` saqlanadi, qolgan ikkisi rad etiladi; ruxsat etilgan oraliq 1–100.
- [ ] **3.9.** Tinch vaqtni `23:00`–`08:00` qiling. Oddiy o‘yin/ball sinovlari oldidan
  ikkalasini ham `00:00` qiling. **Kutiladi:** qiymatlar saqlanadi; teng vaqtlar
  tinch vaqtni vaqtincha o‘chiradi. Sinov oxirida odatdagi qiymatlarni tiklaysiz.
- [ ] **3.10.** Qiymat kiritish savolini ochib, besh daqiqadan keyin javob bering.
  **Kutiladi:** eski savol sozlamani o‘zgartirmaydi; yangi savolni `/sozlamalar` bilan ochish mumkin.
- [ ] **3.11.** A B ni vaqtincha admin qilsin; B sozlamani o‘zgartirsin. Keyin A B ni
  yana oddiy a'zo qilsin va B yana tugmani bossin.
  **Kutiladi:** admin bo‘lganda ruxsat beriladi, huquqi olingach rad etiladi; 10 daqiqa
  kutish kerak emas. Sinov davomida B yana oddiy a'zo bo‘lsin.
- [ ] **3.12.** Telegramda mavjud bo‘lsa, A adminning “Remain Anonymous / Anonim qolish”
  rejimini yoqib `/sozlamalar` va `/vazifa` yuborsin, keyin rejimni o‘chirsin.
  **Kutiladi:** guruh nomidan yozgan admin taniladi. Boshqa kanaldan yuborilgan xabar
  admin deb qabul qilinmaydi. Vazifa yaratilsa uni bajarib yakunlang.

## 4. Kunlik xabar va +1 — 2-bosqich

- [ ] **4.1.** Avtomatik vazifalarni `0` qiling; tinch vaqt o‘chiq bo‘lsin. Bugun hali
  kunlik xabar chiqmagan bo‘lsa, kunlik xabarni yoqing va vaqtini ikki daqiqa oldinga qo‘ying.
  **Kutiladi:** bitta xabar **2–17 daqiqa**, ustiga 30 soniyagacha oraliqda keladi.
  Har bir guruhga barqaror 0–15 daqiqalik qo‘shimcha vaqt qo‘shiladi; bu xato emas.
- [ ] **4.2.** Kelgan xabarni tekshiring.
  **Kutiladi:** `{group}` o‘rniga guruh nomi turadi, matn buzilmagan; odatiy xabarda
  muallif reklama satri yo‘q. `data/daily_messages.json` dagi namunalar ishlatiladi.
- [ ] **4.3.** B va C bir nechta oddiy xabar yozsin; `/men` bilan ballni ko‘rsin.
  **Kutiladi:** kunlik xabardan keyingi birinchi xabari uchun har biriga +1, keyingi
  xabarlariga yana +1 berilmaydi. `/men` kutayotgan ballarni saqlab keyin ko‘rsatadi.
- [ ] **4.4.** Ctrl+C bilan botni to‘xtating, 1.6 dagi buyruq bilan yana ishga tushiring.
  **Kutiladi:** shu kunning kunlik xabari takrorlanmaydi. B yana yozsa ikkinchi +1 olmaydi.
- [ ] **4.5.** Keyingi kunlarda kunlik xabarlarni kuzating.
  **Kutiladi:** uch namuna tugamaguncha bir xil matn qaytarilmaydi; keyin aylanishi mumkin.
  Bugun vaqtni o‘zgartirish shu kun uchun ikkinchi xabar yaratmaydi.
- [ ] **4.6.** Hali xabar chiqmagan kunda kunlik vaqtni yaqinroq qilib, tinch vaqtning
  boshlanishini hozirga, tugashini esa taxminan 20 daqiqa keyinga qo‘ying.
  **Kutiladi:** o‘sha oraliqda xabar chiqmaydi; tinch vaqt tugagach navbatdagi tekshiruvda keladi.
- [ ] **4.7.** Keyingi ball/o‘yin sinovlari oldidan kunlik xabarni o‘chiring va tinch
  vaqtni yana `00:00`–`00:00` qiling. **Kutiladi:** o‘yin ballariga tasodifiy +1 yoki
  yangi avtomatik vazifa aralashmaydi. Har bir sinov **oldidan** `/men` bilan eski
  ballni yozib oling, keyin qo‘shilgan/ayirilgan miqdorni solishtiring.

## 5. Vazifalar, tanlash va reyting — 3-bosqich

Matn vazifasi yoki “Haqiqat” javobi kutilayotganda tanlangan odamning `/men` xabari
ham matn hisoblanadi. Ballni vazifa berilishidan oldin va yakunlangach tekshiring.

- [ ] **5.1.** B `/vazifa video` yuborsin.
  **Kutiladi:** oddiy a'zoga admin emasligi aytiladi; yangi vazifa berilmaydi.
- [ ] **5.2.** A `/vazifa video` yuborsin. Tanlanmagan odam dumaloq video yuborsin;
  tanlangan odam avval ovozli xabar yuborsin.
  **Kutiladi:** vazifada bitta rozilik bergan a'zo va muddati ko‘rsatiladi; bu ikki
  noto‘g‘ri javob vazifani tugatmaydi.
- [ ] **5.3.** Tanlangan odam bot aytgan muddatgacha dumaloq video yuborsin, keyin yana video yuborsin.
  **Kutiladi:** bir marta tabrik va +15; takror video uchun yana +15 yo‘q. Reply qilish shart emas.
- [ ] **5.4.** Yangi guruhdagi uch a'zo hali yaqinda tanlanmagan bo‘lsa, videoli vazifani
  uch marta berib, har safar bajaring. **Kutiladi:** dam olgan boshqa a'zo mavjud bo‘lsa,
  oxirgi 24 soatda tanlangan odam chetlab o‘tiladi. Uchovlon yaqinda tanlangan bo‘lsa
  yana tanlanishi mumkin; bu holatda “har safar boshqa odam” talab qilinmaydi.
- [ ] **5.5.** Vazifa hali bajarilmaganida A yana `/vazifa` yuborsin.
  **Kutiladi:** oldingi vazifa borligi aytiladi; bir guruhda ikkita kutilayotgan vazifa yaratilmaydi.
- [ ] **5.6.** A `/vazifa ovoz`, keyin alohida `/vazifa surat` bersin; har birini mos a'zo bajarsin.
  **Kutiladi:** ovoz va surat uchun +10 dan, faqat kerakli turdagi javobga bir marta beriladi.
- [ ] **5.7.** Matn turini tekshirish uchun botni to‘xtating. `data/challenges.json` ni
  loyiha tashqarisiga zaxiralang va oching:

  ```powershell
  Copy-Item .\data\challenges.json ..\oqibat-challenges-live-backup.json
  notepad .\data\challenges.json
  ```

  So‘ng sinov vaqtida faylga faqat quyidagi namunani yozib saqlang:

  ```json
  [{"key":"live_text_test","kind":"text","text":"Bugungi kuningizni bir gap bilan yozing."}]
  ```

  Botni qayta ishga tushiring; A `/vazifa matn` bersin va tanlangan odam yangi matn yozsin.
  **Kutiladi:** +5 beriladi. Asl uch namunada `text` turi yo‘q, shuning uchun qo‘shimcha
  sinov namunasisiz matn vazifasi topilmasligi tabiiy. Sinov tugagach botni to‘xtating,
  asl faylni quyidagicha tiklang va botni yana ishga tushiring:

  ```powershell
  Copy-Item ..\oqibat-challenges-live-backup.json .\data\challenges.json
  ```
- [ ] **5.8.** A tinch vaqtni hozirni qamraydigan qilib, `/vazifa` yuborsin.
  **Kutiladi:** tinch vaqt tugamaguncha vazifa tayinlanmaydi. Keyin tinch vaqtni o‘chiring.
- [ ] **5.9.** Avtomatik vazifani tekshiring. Masalan, soat 14:00 bo‘lsa, mintaqa
  `Asia/Tashkent`, tinch vaqt tugashi `14:01`, boshlanishi `14:09`, vazifalar soni `1` bo‘lsin.
  **Kutiladi:** taxminan 14:05 da (30 soniyagacha qo‘shimcha) bitta avtomatik vazifa keladi.
  O‘zingizning hozirgi vaqtingizga mos ravishda shu 8 daqiqalik oraliqni tanlang.
- [ ] **5.10.** Shu oraliqda kuniga `2` vazifani, keyin 12 daqiqalik ochiq oraliqda `3`
  vazifani alohida sinang; har birini keyingisidan oldin bajaring.
  **Kutiladi:** `2` ta vazifa ochiq oraliqning 1/4 va 3/4 qismida, `3` tasi 1/6,
  3/6, 5/6 qismida keladi. Oldingi vazifa kutilsa keyingisi ustiga qo‘shilmaydi.
  Oxirida sonni `0`, tinch vaqtni `00:00`–`00:00` qiling.
- [ ] **5.11.** A `/men` va `/top` yuborsin.
  **Kutiladi:** `/men` ball, bajarilgan/o‘tkazilgan vazifalar sonini; `/top` shu hafta
  va jami reytingni ko‘rsatadi. Hafta guruh vaqtida dushanbadan hisoblanadi.
- [ ] **5.12.** B ismini vaqtincha `Sinov <B>&` qilib, oddiy xabar yozsin; bir daqiqa
  kutib `/men` va `/top` ni ko‘ring, keyin ismini tiklasin.
  **Kutiladi:** ism oddiy matn kabi to‘g‘ri ko‘rinadi; HTML buzilmaydi. Yangi ismning
  bazaga saqlanishi taxminan 60 soniyagacha kutishi mumkin.

## 6. Muddati o‘tgan vazifa va jazo — uzoq sinovlar

Bu qadamlarni faqat rozilik bergan sinov a'zolari bilan bajaring. B oddiy a'zo
bo‘lsin. Botning cheklash huquqi va to‘g‘ri `OWNER_ID` kerak. `mute`/`kick` uchun
Telegram guruhi **superguruh** bo‘lishi kerak; oddiy guruhda bu amallar bajarilmaydi.
Eng qisqa oddiy vazifa muddati 2 soat. Qisqa, yashirin “muddatni tugatish” buyrug‘i
yo‘q: bot xabarida ko‘rsatilgan haqiqiy muddatni kuting. Tinch vaqt muddatni uzaytirishi mumkin.

- [ ] **6.1.** `points`, 2 soat, tinch vaqt o‘chiq bo‘lsin. Vazifa olib bajarmang.
  **Kutiladi:** muddati tugagach bir marta −5, o‘tkazilgan vazifalar soni oshadi;
  keyingi kunlik xabarda qarzdor eslatmasi chiqadi. O‘sha qarz yana qayta eslatilmaydi.
- [ ] **6.2.** Keyingi vazifani bajaring.
  **Kutiladi:** odatdagi ball beriladi; ketma-ket o‘tkazishlar hisobi yangidan boshlanadi.
  Bu holat keyingi `kick` chegarasini tekshirishda ham bilinadi.
- [ ] **6.3.** `off` holatida yangi vazifani bajarmay muddatini kuting.
  **Kutiladi:** ball kamaymaydi, a'zo cheklanmaydi/chiqarilmaydi.
- [ ] **6.4.** A va C vaqtincha `/chiqish` yuborsin, faqat B rozilik bergan bo‘lsin.
  A admin sifatida `mute`, muddat `1` kun va `/vazifa` ni tanlasin. B bajarmasin.
  **Kutiladi:** muddat tugaganda B dan −5 va yozish cheklovi; admin A ga cheklov yo‘q.
  Sinovdan keyin A Telegramdan B cheklovini qo‘lda olib tashlasin.
- [ ] **6.5.** B bajargan vazifa bilan ketma-ket o‘tkazish hisobini tozalang. `kick`
  chegarasini `2` qiling va B ikkita yangi vazifani ketma-ket o‘tkazsin.
  **Kutiladi:** birinchisida −5, guruhda qoladi; ikkinchisida yana −5 va guruhdan
  chiqariladi. Taklif havolasi bilan qayta kira oladi, keyin `/qoshilish` ni yangilaydi.
- [ ] **6.6.** Alohida sinovda faqat A rozilik bergan bo‘lsin; A admin/egadir.
  `mute` yoki chegarasi `1` bo‘lgan `kick` vazifasini A o‘tkazsin.
  **Kutiladi:** ball siyosati ishlaydi, lekin admin/ega cheklanmaydi va chiqarilmaydi.
  Oddiy guruh a'zosi bo‘lgan `OWNER_ID` ham alohida avtomatik testda himoyalangan.
- [ ] **6.7.** Botning a'zolarni cheklash huquqini vaqtincha olib, B uchun jazo vazifasini sinang.
  **Kutiladi:** bot yiqilmaydi; ruxsatsiz cheklash/chiqarish amalga oshmaydi. Ball
  jazosi ishlashi mumkin. So‘ng huquqni qaytaring, `points` qoldiring, uchovlon qayta qo‘shiling.
- [ ] **6.8.** Tinch vaqt boshlanishidan oldin berilgan yangi vazifa muddatining oxiri
  tinch vaqtga tushadigan holatni tanlang.
  **Kutiladi:** bot ko‘rsatgan muddat tinch vaqt tugashigacha uzayadi; tinch vaqt ichida
  muddatidan oldin jarima chiqmaydi.

## 7. Duel, viktorina va tanlov — 4-bosqich

Kunlik xabar va avtomatik vazifalarni o‘chirib, uchovlon `/qoshilish` yuboring.

- [ ] **7.1.** B `/duel` yuborsin; 🎲, 🎯, 🎳 tugmalarini B va C sinab ko‘rsin.
  **Kutiladi:** zar turini faqat boshlovchi B tanlay oladi; C duelni qabul qila oladi.
- [ ] **7.2.** C qabul qilgach natijani kuzating.
  **Kutiladi:** bot ikkala zarni doskada yozilgan tartibda tashlaydi. Ikkinchi zar
  animatsiyasi uchun taxminan 4 soniyadan keyin natija, g‘olibga +2 chiqadi.
  Teng bo‘lsa bot o‘zi qayta tashlaydi; tenglikni ko‘rmasangiz shu qismini “hali kuzatilmadi” deb yozing.
- [ ] **7.3.** C ning xabariga javoban B `/duel` yuborsin, A qabul qilishga urinsin.
  **Kutiladi:** faqat C qabul qila oladi. O‘zini yoki qo‘shilmagan odamni duelga
  tanlash rad etiladi.
- [ ] **7.4.** Qabul qilish tugmasini ikki kishi yoki C ketma-ket tez bossin.
  **Kutiladi:** bitta duel boshlanadi, ortiqcha zarlar va takror ball bo‘lmaydi.
  O‘zingiz yuborgan yoki ko‘chirib yuborgan zar botning hisobini almashtirmaydi.
- [ ] **7.5.** Ochiq duelni hech kim qabul qilmasin.
  **Kutiladi:** 90 soniya tugagach yopiladi, ball berilmaydi.
- [ ] **7.6.** B `/viktorina` yuborsin. B bir savolga to‘g‘ri javob bersin, keyin C
  xuddi shu to‘g‘ri javobni bersin. Keyingi savollarda ham qatnashing.
  **Kutiladi:** 5 ta ochiq (anonim emas) quiz, har biriga 30 soniya. Birinchi to‘g‘ri
  javob +5, undan keyingi to‘g‘ri javob +3; noto‘g‘ri javob 0. Bir savoldan takror
  ball olinmaydi; javobni almashtirish yopiq. Uch namunadan 5 savol aylangani uchun takror savol bo‘lishi mumkin.
- [ ] **7.7.** Beshinchi savoldan keyin doska va `/men` ni ko‘ring.
  **Kutiladi:** yangi natija xabarlarini yog‘dirmasdan, avvalgi bitta doska yangilanadi;
  quiz ballari jami ballga qo‘shiladi.
- [ ] **7.8.** Quiz ketayotganda A `/tanla` yoki `/krokodil` yuborsin; B alohida `/duel` ochsin.
  **Kutiladi:** ikkinchi asosiy o‘yin rad etiladi; duel asosiy o‘yin bilan yonma-yon ishlashi mumkin.
  B o‘zining yana ikkinchi faol duelini ocholmaydi. Duel doskasiga reply `/stop` bilan aynan duelni yoping.
- [ ] **7.9.** Bo‘sh guruhda `/tanla` yuboring, uchovlon ovoz bering.
  **Kutiladi:** ikki variantli oddiy, anonim bo‘lmagan so‘rovnoma; 60 soniyadan keyin
  yopiladi, ball bermaydi.
- [ ] **7.10.** B boshlagan o‘yinda C `/stop` yuborsin, keyin B yoki A yuborsin.
  **Kutiladi:** C ga rad javobi; boshlovchi yoki admin o‘yinni to‘xtatadi, faol poll
  ham yopiladi. To‘xtagan o‘yin keyin g‘oliblik ballini bermaydi.
- [ ] **7.11.** Anonim admin rejimi mavjud bo‘lsa, A shu rejimda `/stop` yuborsin.
  **Kutiladi:** admin o‘yinni to‘xtata oladi. Keyin anonim rejimni o‘chiring.
- [ ] **7.12.** Quiz savoli chiqib bo‘lgach botni Ctrl+C bilan to‘xtatib qayta yoqing.
  **Kutiladi:** ochilgan savol takror yuborilmaydi; saqlangan muddatdan keyin o‘yin davom etadi.
  So‘rovnoma/zar yuborilishining ayni o‘rtasida uzilgan noaniq holatlarda esa o‘yin
  qayta boshlash xabari bilan bekor bo‘lishi mumkin; bu avtomatik testda tekshiriladi.

## 8. Krokodil — 5-bosqich

- [ ] **8.1.** B `/krokodil` yuborsin va “So‘zni ko‘rish”ni bossin.
  **Kutiladi:** B birinchi boshlovchi, so‘z faqat uning shaxsiy oynachasida ko‘rinadi;
  guruhga yoki hammaga DM sifatida tarqalmaydi. C bosganda so‘z berilmaydi.
- [ ] **8.2.** B so‘zni tushuntirsin; C to‘liq javobni yozsin.
  **Kutiladi:** C ga +5, B ga +3 va keyingi boshlovchi C bo‘ladi. Begona/noto‘g‘ri
  taxminlar ball bermaydi. `/chiqish` qilgan odamning to‘g‘ri taxmini ham qabul qilinmaydi.
- [ ] **8.3.** `O‘zbekiston` so‘zi kelganda apostrofi boshqa yoki kirillcha
  `Ўзбекистон`, `Ozbekiston!` kabi javobni yozing.
  **Kutiladi:** bir xil so‘z sifatida qabul qilinadi; uzun boshqa gap aynan so‘z taxmini hisoblanmaydi.
- [ ] **8.4.** Boshlovchi so‘zni ikki marta almashtirsin, uchinchi marta ham bossin.
  **Kutiladi:** dastlabki ikkitasi ishlaydi; uchinchisi rad etiladi. Tur uchun
  dastlabki 3 daqiqalik muddat uzaymaydi.
- [ ] **8.5.** Boshlovchi o‘z so‘zini guruhga yozsin, masalan `Bu Mushuk!`.
  **Kutiladi:** −3 ball va shu tur uchun yangi so‘z; boshlovchi o‘sha odam bo‘lib qoladi.
- [ ] **8.6.** Bir turda uch daqiqa hech kim topmasin.
  **Kutiladi:** eski so‘z oshkor bo‘ladi, faqat rozilik berganlardan yangi boshlovchi
  tanlanadi va navbatdagi tur ochiladi.
- [ ] **8.7.** Uch kishi bilan 10 turni tugating.
  **Kutiladi:** 10-turdan keyin o‘yin tugaydi, natija doskasi yangilanadi, yana tur ochilmaydi.
- [ ] **8.8.** Boshqa o‘yinda `/stop` ni, yana boshqasida tur o‘rtasida Ctrl+C va
  qayta ishga tushirishni sinang. **Kutiladi:** stop bekor qiladi; qayta yoqilgan bot
  saqlangan so‘z/turni davom ettiradi, o‘tgan muddatni hisobga oladi.

## 9. Haqiqat yoki jasorat — 6-bosqich

- [ ] **9.1.** B `/hyj` yuborsin, keyin alohida o‘yinda C xabariga reply `/hyj` yuborsin.
  **Kutiladi:** birinchida rozilik berganlardan tasodifiy odam, ikkinchisida aynan C
  tanlanadi. Birinchi o‘yinni `/stop` bilan tugatib keyingisini boshlang.
- [ ] **9.2.** C tanlangan o‘yinda B va A tanlov/rad etish tugmalarini bossin.
  **Kutiladi:** faqat C bosishi mumkin. Guruh administratori ham C o‘rniga tanlamaydi.
- [ ] **9.3.** C “Haqiqat”ni tanlasin, avval B javob bersin, keyin C yangi matn yozsin.
  **Kutiladi:** o‘zbekcha savol chiqadi; B uni tugatmaydi. C ning 30 daqiqadagi
  matni +5 beradi va o‘yin tugaydi; yana matn yozish ikkinchi +5 bermaydi.
- [ ] **9.4.** Yangi “Haqiqat”da C ovozli xabar yuborsin.
  **Kutiladi:** ovoz ham +5 beradi; surat/dumaloq video haqiqat javobi hisoblanmaydi.
- [ ] **9.5.** Haqiqatni javobsiz 30 daqiqa, alohida tanlovni javobsiz 90 soniya qoldiring.
  **Kutiladi:** har biri tugaydi, qo‘shimcha ball jazosi yoki cheklash yo‘q.
- [ ] **9.6.** Oddiy kutilayotgan vazifa yo‘q va tinch vaqt o‘chiq bo‘lsin. C “Jasorat”ni tanlasin.
  **Kutiladi:** C ga aynan mavjud vazifa tizimi orqali vazifa va taxminan 1 soatlik
  muddat beriladi. Tinch vaqtga tushgan oxiri tinch vaqt tugashigacha uzayadi.
- [ ] **9.7.** C vazifada so‘ralgan turdagi javobni yuborsin.
  **Kutiladi:** dumaloq video +15, ovoz/surat +10, matn +5; o‘yin va bog‘liq vazifa
  birga tugaydi. Qolgan turlarni alohida o‘yinlarda tekshiring. Matn uchun 5.7 dagi
  vaqtinchalik bank kerak; har gal asl bankni tiklab botni qayta yoqing.
- [ ] **9.8.** Oddiy vazifa hali kutilayotgan paytda yangi HYJ tanlovida “Jasorat”ni bosing.
  **Kutiladi:** ikkinchi vazifa yaratilmaydi; “Haqiqat”ni tanlash mumkin. Tinch
  vaqtda jasorat so‘ralsa ham yangi vazifa tayinlanmaydi.
- [ ] **9.9.** Tanlov paytida, keyin alohida o‘yinda haqiqat/jasorat berilgach,
  tanlangan odam “Rad etish”ni bossin.
  **Kutiladi:** har bir o‘yinda faqat −2; jasorat vazifasi bekor bo‘ladi. Guruhda
  `mute`/`kick` tanlangan bo‘lsa ham **qabul qilingan rad etish** hech kimni cheklamaydi/chiqarmaydi.
- [ ] **9.10.** Rad etish tugmasini bir necha marta tez bosing; alohida sinovda
  vazifa javobini yuborish bilan bir paytda rad etishga urining.
  **Kutiladi:** bitta natija: yo bajarish balli, yo −2. Ikkalasi birga berilmaydi.
  Muddati allaqachon tugagan yoki bajarilgan vazifani keyin rad etib o‘zgartirib bo‘lmaydi.
- [ ] **9.11.** Jasoratni rad etmay 1 soatlik haqiqiy muddatigacha bajarmang.
  **Kutiladi:** oddiy vazifa jazosi (`off`/`points`/`mute`/`kick`) ishlaydi. Bu rad
  etishdan boshqa holat; jazo sinovi 6-bo‘limdagi rozilik va huquqlar bilan bajariladi.
- [ ] **9.12.** Jasorat kutilayotganda tanlangan odam `/chiqish` yuborsin; alohida
  o‘yinda boshlovchi `/stop` yuborsin. **Kutiladi:** o‘yin va vazifa jarimasiz bekor
  bo‘ladi, keyin eski javob ball bermaydi. Qayta qatnashish uchun `/qoshilish` kerak.
- [ ] **9.13.** Savol yoki jasorat to‘liq chiqib bo‘lgach botni qayta yoqing.
  **Kutiladi:** saqlangan holat/muddat davom etadi; ball takrorlanmaydi. Aynan savol
  yuborish o‘rtasidagi noaniq uzilishda qayta boshlash xabari bilan bekor bo‘lishi mumkin.

## 10. Migratsiya va katta guruhlar uchun tayyorgarlik — 0.5 va Claude tuzatishlari

- [ ] **10.1.** Telegram mijozingiz ruxsat bersa, ball va kutilayotgan vazifasi bor
  oddiy guruhni superguruhga aylantiring. **Kutiladi:** sozlama, a'zolar roziligi,
  ball va vazifa yangi guruhda saqlanadi; eski guruhga navbatdagi xabar ketmaydi.
  Botni qayta yoqib `/men` ni tekshiring va eski vazifani yangi guruhda bajaring.
  Allaqachon superguruh bo‘lsa yoki aylantirish yo‘li mavjud bo‘lmasa `Mos emas`
  deb yozing; to‘liq ko‘chirish/qaytarish holatlari avtomatik testda bor.
- [ ] **10.2.** Oddiy suhbatni davom ettirib, botni besh daqiqa ishlating.
  **Kutiladi:** jurnalda `queue_length`, `updates_per_minute`, `last_tick_duration_ms`
  satri chiqadi. Ketma-ket ko‘p o‘yinlardan so‘ng guruhga xabarlar kechikishi mumkin:
  bot butun tizimga 25/soniya, bir chatga 18/daqiqa chegarasini saqlaydi. Tugma
  oynachalari xabar navbatiga kirmaydi. Navbatda avval o‘yinlar, so‘ng vazifalar,
  so‘ng kunlik xabarlar turadi. Guruhga sun'iy xabar yog‘dirish talab qilinmaydi.
- [ ] **10.3.** Ikkinchi PowerShellda quyidagi tekshiruvlarni bajaring:

  ```powershell
  .\.venv\Scripts\pytest.exe -q tests/test_scale_limiter.py tests/test_scale_schedule.py tests/test_scale_activity.py tests/test_scale_state.py tests/test_scale_scheduler.py tests/test_scale_runtime.py tests/test_claude_review.py
  .\.venv\Scripts\python.exe scripts\simulate_load.py --ticks 10
  ```

  **Kutiladi:** testlar o‘tadi. Ular 25/soniya va 18/daqiqa, ustuvor navbat,
  429 kutish/qayta urinish, 60 soniyalik yig‘ib yozish, SQLsiz oddiy xabarlar,
  admin keshi, o‘yin qulflari, alohida muddat sikli va 10 daqiqalik xato ortga
  surilishini tekshiradi. Simulyatsiyada 5 000 soxta chat, har turga 500 tadan
  cheklov va yakunda `total_due_items_processed=15000`, `remaining_due_daily=0`
  chiqadi. Bu haqiqiy Telegramga xabar yubormaydi va shaxsiy bazani o‘zgartirmaydi;
  10 000 haqiqiy guruhga tayyorlik isboti emas.
- [ ] **10.4.** Faqat tayyor PostgreSQL serveringiz bo‘lsa, alohida sinov bazasi va
  `postgresql+asyncpg://...` manzilini `.env` ga yozing, `ENVIRONMENT=production`,
  `DB_POOL_SIZE=15` bilan migratsiya va `scripts/check_env.py` ni bajaring.
  **Kutiladi:** ulanish/jadval tekshiruvi o‘tadi; production rejimi SQLite bilan
  ishlashga ruxsat bermaydi. Server bo‘lmasa `Mos emas`. Mahalliy tekshiruvga qaytganda
  avvalgi `.env` qiymatlarini tiklang.
- [ ] **10.5.** Faqat tayyor HTTPS domen/server bo‘lsa, README dagi webhook
  bo‘limi orqali `USE_WEBHOOK`, `WEBHOOK_URL`, `WEBHOOK_SECRET`, `WEBHOOK_HOST`,
  `WEBHOOK_PORT` ni sozlang va botni qayta yoqing.
  **Kutiladi:** `/start` va guruh tugmalari webhook orqali ham ishlaydi; noto‘g‘ri
  maxfiy sarlavhali so‘rov rad etiladi (bu holat mahalliy avtomatik testda ham bor).
  Pollingga qaytish uchun botni to‘xtatib `USE_WEBHOOK=false` bilan qayta yoqing.
  Bir paytda ikkala rejim ishlatilmaydi. Server bo‘lmasa `Mos emas`.

## 11. Biror qadam ishlamasa: jurnaldan xatoni topish

- [ ] **11.1.** Xato bo‘lgan vaqtni, buyruqni, A/B/C dan kim bajarganini va kutilgan
  natijani yozing. **Kutiladi:** masalan “18:42, B, /hyj → Haqiqat; savol chiqishi kerak,
  lekin tugma aylanib qoldi” kabi qayta tekshirishga yetadigan yozuv bo‘ladi.
- [ ] **11.2.** Ikkinchi PowerShellda oxirgi satrlarni va xato atrofini ko‘ring:

  ```powershell
  Get-Content .\bot-live.log -Tail 80
  Select-String -Path .\bot-live.log -Pattern 'ERROR|WARNING|Traceback|retry_after|backing off' -Context 3,12
  ```

  **Kutiladi:** sana/vaqt, daraja (`INFO`, `WARNING`, `ERROR`), modul nomi, xato
  sababi ko‘rinadi. `Traceback` bo‘lsa undan keyingi oxirgi satr xato turini aytadi;
  undan yuqoridagi `File ... line ...` qaysi fayl/qator ekanini ko‘rsatadi.
  Jurnal kompyuter/server vaqtidan foydalanadi; hisobotga uning vaqtini ham ko‘chiring.
- [ ] **11.3.** Quyidagi belgilarni ajrating. **Kutiladi:** sababga mos qadam tanlanadi:

  | Jurnaldagi yozuv | Nima tekshiriladi |
  | --- | --- |
  | `Unauthorized`, token xatosi | `.env`, BotFatherdagi joriy token; `check_env.py` ni qayta bajaring |
  | `Conflict` | Shu token bilan boshqa bot nusxasi yoki webhook ishlamayaptimi? |
  | `TelegramNetworkError`, vaqt tugashi | Internet va Telegramga ulanish |
  | `Telegram rate limit`, `retry_after` | Bot aytgan vaqtni kuting; qayta ishga tushirib cheklovni aylanmang |
  | `Scheduled ... failed`, `backing off` | Shu chatdagi ish 10 daqiqaga surilgan; yuqoriroqdagi asl xatoni toping |
  | `Telegram operation failed` | Shu satr ostidagi traceback, bot huquqlari va Telegram xabari |
  | `Permission check failed`, `requires a supergroup` | Botning cheklash huquqi va guruh turi |
  | `Admin refresh failed` | Telegram ulanishi va botning adminligi; ruxsat tasdiqlanmasa amal rad etiladi |
  | `no such table`, `Migration missing`, schema xatosi | Botni to‘xtatib `alembic upgrade head`, keyin `check_env.py` |
  | `Could not migrate Telegram chat` | Eski/yangi guruh IDlari va shu satr atrofidagi tracebackni Claude ko‘rsin |
  | `Unhandled error processing update` | Update raqami, vaqt va to‘liq tracebackni yozib oling |

- [ ] **11.4.** Oddiy kunlik xabar ko‘rinmasa avval vaqt mintaqasi, yoqilganligi,
  tinch vaqt, 0–15 daqiqa qo‘shimcha va shu kunning xabari oldin chiqqanini tekshiring.
  **Kutiladi:** tabiiy kutish bilan xatoni ajratasiz. Jurnalda yuborish xatosi bo‘lsa,
  yo‘qolgan javob sabab takror xabar chiqmasligi uchun o‘sha kun avtomatik qayta
  yuborilmasligi mumkin; buni Claude uchun qayd qiling.
- [ ] **11.5.** Claude uchun xato vaqti, takrorlash qadamlari, kutilgan/haqiqiy natija
  va tegishli 20–50 jurnal satrini tayyorlang. **Kutiladi:** token, baza paroli,
  `WEBHOOK_SECRET`, `.env` va kerakmas shaxsiy ma'lumotlar ulashilmaydi. Bot
  sozlangan maxfiy qiymatlarni `[REDACTED]` bilan yopadi; baribir yuboriladigan
  parchani ko‘zdan kechiring. `bot-live.log` va `.env` Gitga qo‘shilmaydi.

## 12. Sinovni yakunlash va Claude uchun material

- [ ] **12.1.** O‘zgartirilgan ism, admin huquqi, cheklov va vaqtinchalik kontentni
  tiklang; sinov guruhi sozlamalarini kerakli holatga qaytaring.
  **Kutiladi:** asl uch namunali banklar qoladi, kerakmas vazifa/o‘yinlar `/stop`
  bilan tugagan; guruh va a'zolar keyingi tekshiruvga tayyor.
- [ ] **12.2.** Ctrl+C bilan botni to‘xtating. Keyin quyidagilarni bajaring:

  ```powershell
  .\.venv\Scripts\pytest.exe -q
  .\.venv\Scripts\ruff.exe check .
  .\.venv\Scripts\alembic.exe check
  git status --short
  git rev-parse --short HEAD
  ```

  **Kutiladi:** testlar, kod tekshiruvi va migratsiya tekshiruvi o‘tadi. Oxirgi
  commit raqamini sinov qaydiga yozing. Vaqtinchalik kontent o‘zgarishi qolsa
  zaxiradan tiklang; o‘z yangi haqiqiy kontentingizni alohida saqlang.
- [ ] **12.3.** Joriy saqlangan commitdan loyiha tashqarisiga ko‘rib chiqish arxivini oling:

  ```powershell
  git archive --format=zip -o "..\oqibat-review.zip" HEAD
  ```

  **Kutiladi:** `D:\Coding projects\oqibat-review.zip` yaratiladi; faqat commitdagi
  fayllar kiradi. `.env`, jurnal, mahalliy baza va `.venv` arxivda bo‘lmaydi.
  Claude ga shu ZIP va belgilangan ro‘yxat/xato qaydini bering.
- [ ] **12.4.** Natijani yozing. **Kutiladi:** ochiq muammolar va bajarilmagan uzoq
  sinovlar yashirilmaydi; natijalar Claude yakuniy ko‘rib chiqishi uchun tayyor bo‘ladi.

```text
Sana va vaqt (Asia/Tashkent):
Commit:
A / B / C:
O‘tgan bo‘limlar:
Ishlamagan qadam raqamlari:
Kutilgan va haqiqiy natija:
Jurnaldagi vaqt / update raqami:
Keyinga qolgan yoki mos bo‘lmagan sinovlar va sababi:
```

BotFather va admin xabar ko‘rishi bo‘yicha rasmiy manbalar:
[Telegram boshlang‘ich qo‘llanmasi](https://core.telegram.org/bots/tutorial),
[Telegram botlar FAQ](https://core.telegram.org/bots/faq#what-messages-will-my-bot-get).


## 13. Mafia — kamida besh kishi

- [ ] **13.1.** Kamida besh haqiqiy sinov a'zosi guruhda `/qoshilish` yuborsin.
  Bittasi `/mafia` yuborsin, hammalari tugmadagi havolani bosib shaxsiy chatda Start qilsin.
  **Kutiladi:** 90 soniyalik kutish ro‘yxati bitta xabarda yangilanadi; guruhdagi
  oddiy tugma yoki yozuv bilan qo‘shilish yo‘q. Beshdan kam bo‘lsa o‘yin bekor bo‘ladi.
- [ ] **13.2.** Boshqa guruhda ham Mafia ochib, shu foydalanuvchi bilan qo‘shilishga urining.
  **Kutiladi:** bir paytda bitta Mafia kutish/o‘yiniga qatnashish mumkin. Eski yoki
  yopilgan havola yangi o‘yinga qo‘shmaydi.
- [ ] **13.3.** Olti kishi qo‘shilsin; bittasi boshlanishdan oldin botni bloklasin.
  **Kutiladi:** unga rol yetkazilmasa ro‘yxatdan olinadi va guruhda aytiladi. Qolgan
  besh kishi uchun rollar qayta hisoblanadi. Faqat to‘rt kishi qolsa bekor qilinadi.
  Dastlabki rol yangilansa eski taklif bekor; tasdiqlangan rol va tugmalarni kuting.
- [ ] **13.4.** Rollarni shaxsiy chatda ko‘ring. Tunda mafia nishon tanlasin, doktor
  bir kishini saqlasin, komissar bir kishini tekshirsin.
  **Kutiladi:** mafia sheriklarini va faqat o‘zlariga ko‘rinadigan jonli ovoz hisobini
  ko‘radi. Komissar javobi faqat o‘ziga chiqadi. Mafia umuman ovoz bermasa hujum yo‘q.
- [ ] **13.5.** Tunni 60 soniya kuting, keyin 90 soniya muhokama va 60 soniya ovoz bering.
  **Kutiladi:** tongda qurbon yoki doktor saqlagani aytiladi, chiqqan odam roli ochiladi.
  Guruh ovozlari bitta doskada yangilanadi, ovozni almashtirish mumkin; teng bo‘lsa hech kim chiqmaydi.
- [ ] **13.6.** O‘yindan chiqqan odam ovoz bersin. Keyingi turda eski tugmalarni bosing.
  **Kutiladi:** oynachada rad etiladi; holat va ball o‘zgarmaydi. Doktor o‘zini ketma-ket
  ikki kecha saqlay olmaydi; komissar bir kechada faqat bir tekshiruv qiladi.
- [ ] **13.7.** `/sozlamalar` da chiqqanlarning xabarini o‘chirishni tekshiring.
  **Kutiladi:** dastlab o‘chiq. Yoqilganda va botda o‘chirish huquqi bo‘lsa o‘yindan
  chiqqan a'zoning yangi guruh xabari o‘chiriladi; tirik odamning xabari qoladi.
- [ ] **13.8.** O‘yinni oxirigacha o‘ynang; alohida sinovlarda `/stop` va botni qayta yoqishni tekshiring.
  **Kutiladi:** tinch aholi yoki mafia g‘olib bo‘ladi, g‘olib tomonga +10 va tirik qolganlarga +3.
  20 tur/60 daqiqa chegarasi durang qiladi. Stop yoki qayta yoqish bekor qiladi va
  ishtirokchilarga shaxsiy xabar beradi; bekor qilingan o‘yinga ball berilmaydi.


## 14. Haftalik xulosa va yordam

- [ ] **14.1.** Guruhda hafta davomida kunlik qatnashish, vazifa va o‘yinlardan ball oling.
  Botni yakshanba guruh vaqti 20:00–21:00 orasida ishlating.
  **Kutiladi:** shu haftaning bitta xulosasi: top 5, eng faol a'zo, bajarilgan/o‘tkazilgan
  vazifalar, kutilayotganlar, shior, muallif va guruhga qo‘shish tugmasi chiqadi.
  Eng faol — xabarlar soni emas, ball keltirgan alohida ishtiroklar soni.
- [ ] **14.2.** Xulosa chiqqach botni qayta yoqing. Alohida haftada xulosa vaqti tinch
  vaqtga tushsin va tinch vaqt dushanba ertalab tugasin.
  **Kutiladi:** qayta yoqish takror xulosa bermaydi; dushanbaga surilgan xulosa oldingi
  haftaga tegishli bo‘ladi, keyingi yakshanbaning xulosasi o‘z vaqtida chiqishi mumkin.
- [ ] **14.3.** Shaxsiy chatda va guruhda `/help` yuboring.
  **Kutiladi:** barcha 0–7-bosqich buyruqlari, o‘yin vaqtlari, shior, muallif va guruhga
  qo‘shish tugmasi bor. Oddiy vazifa/o‘yin xabarlariga muallif satri qo‘shilmaydi.

## 15. Rasmli natijalar va serverga tayyorlik

- [ ] **15.1.** `.env` da `RESULT_CARDS_ENABLED=true` bo‘lsin. Ismida Oʻtkir,
  Gʻulom yoki Ўткир bo‘lgan a'zo bilan duel/viktorina/Krokodilni yakunlang.
  **Kutiladi:** oxirgi matnli doska va bitta natija rasmi chiqadi. Ismlar, ballar
  hamda Instagram belgisi aniq ko‘rinadi; uzun ism rasm tashqarisiga chiqmaydi.
- [ ] **15.2.** Haqiqat va jasoratni bajaring, alohida sinovda rad eting yoki `/stop` qiling.
  **Kutiladi:** bajarilgan haqiqat +5 yoki jasoratning tegishli balli rasmda ko‘rinadi.
  Rad etilgan/bekor o‘yinda g‘olib rasmi yo‘q. Mafia g‘olib jamoasi rasmi top 5 ni ko‘rsatadi.
- [ ] **15.3.** Yakshanba xulosasini kuting; kelgach botni qayta yoqing.
  **Kutiladi:** bitta top-5 rasm, tagida to‘liq vazifa/eng faol xulosasi va qo‘shish
  tugmasi bor. Shu haftaning xulosasi qayta yuborilmaydi.
- [ ] **15.4.** `RESULT_CARDS_ENABLED=false` qilib botni qayta yoqing va yangi duel o‘ynang.
  **Kutiladi:** oddiy yakuniy doska/ballar ishlaydi, yangi rasm kelmaydi.
- [ ] **15.5.** README dagi Docker yoki systemd yo‘lini faqat alohida sinov muhiti
  va sinov botida bajaring. Avval migratsiya, `python -m bot --check`, so‘ng checker.
  **Kutiladi:** baza tayyor, getMe/username to‘g‘ri, faqat bitta bot jarayoni ishlaydi.
  Boshqa Docker loyihalari o‘zgarmaydi; `.env` obrazga yoki Git ga kirmaydi.
- [ ] **15.6.** README bo‘yicha bazadan nusxa oling va yangi bo‘sh sinov bazasiga tiklang.
  **Kutiladi:** nusxa fayli bor, tiklash xatosiz; asl baza saqlanadi. Jurnalni ochib
  xato va besh daqiqalik navbat/yangilanish/tick ko‘rsatkichlarini topa olasiz.
