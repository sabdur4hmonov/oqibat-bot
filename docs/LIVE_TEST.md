# Oqibat: to‘liq jonli sinov ro‘yxati (0–21-bosqichlar)

Faqat alohida **sinov botida va sinov guruhida** bajaring. Uch odam: **A** — bot egasi
va guruh admini, **B** va **C** — oddiy a’zolar. Har qadamni faqat o‘tgach belgilang.
Har bo‘limdan oldin ochiq o‘yinni `/stop` bilan tugating. Haqiqiy guruhni yoki
ishlab turgan bazani bu sinov uchun buzib qo‘ymang.

**Chegara:** uch kishi bilan to‘liq Mafia o‘ynab bo‘lmaydi: oddiy Mafia kamida 5,
Don 8, Ma’shuqa 9, Manyak 11 qatnashuvchi talab qiladi. Uchlikda kamlik sababli
bekor bo‘lish va sozlamalar sinaladi. Quyidagi alohida Mafia bo‘limi uchun yetarli
haqiqiy a’zo qo‘shilmasa, qadamlarni belgilamang — “jonli tekshirilmagan” deb yozing.
Avtomatik testlar haqiqiy odamlar bilan sinov o‘rnini bosmaydi.
Kim aytdi? va Telefonning to‘liq sinovi uchun **D — to‘rtinchi haqiqiy odam** kerak.
Yashirin topshiriq va Eslaysizmi? uch kishi bilan to‘liq sinaladi. Yashirin uchun
kamida 4 ta turli so‘z tayyorlang: repodagi uchta namuna formatni ko‘rsatadi.

## 1. Tayyorlash: BotFather, muhit va ishga tushirish (0, 0.5)

- [ ] A BotFather orqali alohida bot ochsin, haqiqiy token va o‘zining yangi username’ini olsin.
  **Natija:** botning aniq egasi A; `OqibatBot` boshqa odamniki, misoldagi `YourBotUsername` ham almashtiriladi.
- [ ] Loyiha papkasida PowerShell oching va virtual muhitni tayyorlang:

  ```powershell
  py -3.12 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements-dev.txt
  if (-not (Test-Path .env)) { Copy-Item .env.example .env }
  notepad .env
  ```

  **Natija:** runtime va test kutubxonalari o‘rnatiladi. Bor `.env` ni ko‘r-ko‘rona ustiga yozmang.
- [ ] `.env` da BOT_TOKEN, haqiqiy BOT_USERNAME, INSTAGRAM_HANDLE va A ning raqamli
  OWNER_ID sini yozing (telefon/username emas). Mahalliy sinovga `ENVIRONMENT=development`,
  `USE_WEBHOOK=false`, `WEBAPP_URL=`, `DATABASE_URL=sqlite+aiosqlite:///./oqibat-live.db` tanlang.
  **Natija:** alohida sinov bazasi ishlatiladi; token va parol Gitga kirmaydi.
- [ ] Quyidagilarni bajaring:

  ```powershell
  alembic upgrade head
  python -m bot --check
  python scripts/check_env.py
  python -m bot 2>&1 | Tee-Object -FilePath bot-live.log
  ```

  **Natija:** migratsiya va offline tekshiruv o‘tadi; checker getMe/username/bazani
  tasdiqlaydi; bot ishlaydi. Xatoda shu yerda to‘xtab sozlamani tuzating.
- [ ] A, B, C botning shaxsiy chatida `/start`, keyin `/help` va `/oyinlar` yuborsin.
  **Natija:** o‘zbekcha javob, shior va kerakli qo‘shish tugmasi; muallif satri /start
  va /help da bor, oddiy o‘yin xabarlariga har safar qo‘shilmaydi. /oyinlar 9 o‘yinni ko‘rsatadi.
- [ ] Ismda `Oʻtkir`, `Gʻulom`, `<Sinov & do‘st>` kabi belgilarni sinab ko‘ring.
  **Natija:** ism matn sifatida chiqadi, HTML buyruqqa aylanmaydi. Keyin asl ismni tiklang.

## 2. Guruhga qo‘shish, rozilik va sozlamalar (1)

- [ ] A uch kishilik yopiq guruh ochsin. Botni avval oddiy a’zo qilib qo‘shing.
  **Natija:** bot admin qilishni tushuntiradi; o‘yin/vazifalar boshlanmaydi.
- [ ] Botni admin qiling, xabar o‘chirish va a’zolarni cheklash huquqlarini bering.
  **Natija:** salomlashuv va qo‘shilish tugmasi chiqadi; adminlikda kerakli xabarlarni ko‘radi.
- [ ] A/B/C `/qoshilish` yoki qo‘shilish tugmasini bossin; yana bosib ko‘rsin.
  **Natija:** har kim bir marta ro‘yxatga olinadi, takror bosish dubl yaratmaydi.
- [ ] B `/chiqish` qilsin; keyin yangi rozilik bilan qayta qo‘shilsin.
  **Natija:** chiqqanda yangi tasodifiy vazifa/o‘yinga olinmaydi; qayta qo‘shilish ishlaydi.
- [ ] B guruhdan chiqib qaytsin; `/qoshilish` ni yana bajarsin.
  **Natija:** ketgan a’zo faol ro‘yxatdan chiqadi; qaytish eski rozilikni o‘z-o‘zidan tiklamaydi.
- [ ] B `/sozlamalar`, keyin A chiqargan sozlama tugmasini bossin.
  **Natija:** oddiy a’zo sozlay olmaydi; A admin bo‘lib sozlay oladi.
- [ ] A `/sozlamalar` dagi barcha maydonlarni birma-bir o‘zgartirib qaytarsin:
  kunlik yoqish/vaqt, vaqt mintaqasi, kunlik vazifa soni, vazifa muddati, jazo turi,
  mute kunlari, kick chegarasi, tinch vaqtlar, Mafia o‘lik xabarlarini o‘chirish,
  kengaytirilgan rollar. Noto‘g‘ri vaqt/qiymat ham kiriting.
  **Natija:** ruxsat etilgan qiymat saqlanadi, noto‘g‘risi rad etiladi; qayta yoqilganda saqlanib qoladi.
- [ ] A anonim admin rejimida `/sozlamalar` va `/vazifa` ni sinasin, so‘ng rejimni o‘chirsin.
  **Natija:** o‘z guruhidan yozayotgan anonim admin taniladi; boshqa kanal nomidan yozish adminlik bermaydi.
- [ ] Botni olib tashlab qayta qo‘shing/admin qiling.
  **Natija:** chiqarilganda guruh nofaol, qaytganda ishlay oladi; ikki marta bir xil qayd yaratilmaydi.

## 3. Kunlik xabar, tinch vaqt va ballar (2, 3)

- [ ] Kunlik vaqtni 2 daqiqa oldinga qo‘ying, tinch vaqt tashqarisida kuting.
  **Natija:** barqaror 0–15 daqiqa qo‘shimcha sabab xabar **2–17 daqiqada** kelishi mumkin;
  guruh nomi xavfsiz qo‘yiladi. Shu kunning xabari oldin chiqqan bo‘lsa ikkinchisi chiqmaydi.
- [ ] Xabardan keyin B bir necha marta yozsin, `/men` ni ochsin.
  **Natija:** shu mahalliy kun uchun bir marta +1; har yozishga ball berilmaydi.
- [ ] Botni Ctrl+C bilan to‘xtatib qayta yoqing.
  **Natija:** tasdiqlangan kunlik xabar va +1 ball takrorlanmaydi.
- [ ] Kunlik vaqtni tinch vaqt ichiga qo‘ying; keyin tinch vaqt tugashini kuting.
  **Natija:** tinch paytda yangi post/vazifa yo‘q, keyin tegishli vaqtga suriladi.
- [ ] Namuna bankdagi turli kunlik xabarlarni keyingi kunlarda kuzating.
  **Natija:** hammasi ishlatilmaguncha shu guruhda takrorlanmaydi; keyin eng eski ishlatilgani qaytishi mumkin.

## 4. Vazifalar, jarimalar va reyting (3)

- [ ] Tinch vaqtni tashqarida qoldiring. Faqat B ni vaqtincha rozilikda qoldirib,
  A `/vazifa video` yuborsin. B oddiy video, so‘ng **davra videosi** yuborsin.
  **Natija:** oddiy video hisoblanmaydi; davra videosi vazifani tugatib +15 beradi.
- [ ] Shu faylni/takror javobni yana yuboring, boshqa odam ham bajarsin.
  **Natija:** bitta vazifaga ball ikki marta yozilmaydi; faqat tanlangan odam bajaradi.
- [ ] `/vazifa ovoz`, `/vazifa surat` ni bajaring. Matn vazifasi kerak bo‘lsa faqat
  sinov kontent nusxasiga qo‘llanma bo‘yicha `kind: text` yozib, validator va restart qiling.
  **Natija:** ovoz/rasm +10, matn +5; noto‘g‘ri tur tugatmaydi. Eski kontentni keyin qaytaring.
- [ ] Barcha uch kishini qayta qo‘shing. Oddiy B `/vazifa` yuborsin; A kutayotgan vazifa borida yana bersin.
  **Natija:** admin bo‘lmagan rad etiladi; bir guruhda bittadan ortiq kutayotgan vazifa yo‘q.
- [ ] Bir vazifani bajarmasdan uning haqiqiy muddatini kuting. Tugashi tinch vaqtga tushsin.
  **Natija:** muddat tinch vaqt oxiriga suriladi; keyin missed va tanlangan jarima ishlaydi.
  Qisqa tekshiruv uchun pastdagi avtomatik deadline testlarini ishlating; server vaqtini o‘zgartirmang.
- [ ] Alohida urinishlarda jazo `off` va `points` bo‘lsin.
  **Natija:** off da jarima yo‘q; points da −5 va keyingi kunlik xabarda qarzdor eslatmasi chiqadi.
- [ ] Faqat rozi B bilan sinov superguruhida mute, keyin kick rejimini tekshiring;
  A qayta taklif havolasini tayyorlasin. Kick chegarasigacha ketma-ket qoldiring.
  **Natija:** tegishli huquq bo‘lsa mute ishlaydi; kick faqat chegaradan keyin, qayta kirish mumkin.
  A/admin/bot egasi hech qachon mute/kick qilinmaydi; huquq yo‘qligida cheklash o‘tkazib yuboriladi.
- [ ] B yangi vazifani bajarsin; `/men`, `/top` ni tekshiring.
  **Natija:** ketma-ket qoldirish hisoblagichi tiklanadi; joriy mavsum va barcha vaqt ballari to‘g‘ri.

## 5. Tez o‘yinlar (4, 15, 16)

- [ ] A `/duel` yuborsin, B qabul qilsin; keyin B xabariga javoban yana taklif qiling.
  🎲/🎯/🎳 ni sinang. C maqsadli duelni qabul qilishga urinsin.
  **Natija:** tegishli raqib tanlanadi, zarni bot ikki tomonga tashlaydi; animatsiya uchun taxminan
  4 soniya kutiladi. Tenglikda qayta tashlanadi, g‘olibga +2 bir marta.
- [ ] `/viktorina` o‘ynang: 5 ta 30 soniyalik savolga uchalasi javob bersin.
  **Natija:** anonim bo‘lmagan quiz; to‘g‘ri javob +3, birinchi to‘g‘ri javobga yana +2;
  yakuniy jadval bitta doskada yangilanadi.
- [ ] `/tanla` da ikki variantdan ovoz bering, keyin `/stop` qiling.
  **Natija:** oddiy anonim bo‘lmagan tanlov; quiz ballari berilmaydi, so‘rov tugatiladi.
- [ ] `/tqq` oching, B qabul qilsin. A Toshni, B Qaychini tanlasin.
  **Natija:** ikkala tanlovgacha faqat tayyorlik ko‘rinadi; keyin ikkalasi ochiladi, A ga +2.
- [ ] RPS da teng tanlov, maqsadli reply, uchinchi odam, ko‘p bosish va eski tugmani sinang.
  **Natija:** durangda ball yo‘q; faqat taklif qilingan raqib qabul qiladi; birinchi tanlov qulflanadi;
  begona/eski/takror tugma ball yozmaydi. `/toshqaychiqogoz` ham ishlaydi.
- [ ] RPS ni 90 soniya qabul qilmay, alohida o‘yinda qabul qilib 60 soniya tanlamay kuting.
  **Natija:** ballsiz tugaydi; yolg‘iz tanlov ochilmaydi. O‘yinchi chiqsa ham bekor bo‘ladi.
- [ ] `/sontop` yuboring. **O‘yin xabariga javob** qilib 50 yozing, keyingi taxminlarni toraygan oraliqda yuboring.
  **Natija:** kattaroq/kichikroq yoki darhol topilgan natija; topuvchiga +3 bir marta.
- [ ] Son o‘yinida oddiy chatga 50, reply orqali 101 va juda tez takror taxmin yuboring.
  **Natija:** hisoblanmaydi; har odam 3 soniya kutadi. 15 valid urinish yoki 3 daqiqa tugasa son ochiladi, ball yo‘q.
- [ ] `/matematika` dagi 5 savolga tugmalar bilan javob bering. B birini noto‘g‘ri, C to‘g‘ri bossin.
  **Natija:** B ga shaxsiy xato popup, shu savolda qayta urinish yo‘q; C ga +2 va yangi savol.
  Eski raund tugmasi ishlamaydi. Oxirida jami jadval, qo‘shimcha yakun balli yo‘q.
- [ ] Matematikada bir savolni 20 soniya javobsiz qoldiring.
  **Natija:** javob ochilib keyingisiga o‘tadi; vaqt xabar yetkazilgach boshlanadi.
- [ ] Har o‘yinda `/stop` ni boshlovchi/admin, keyin oddiy uchinchi odam bilan sinang.
  **Natija:** faqat boshlovchi/admin to‘xtatadi; tugagan o‘yin yangi javob qabul qilmaydi.
  Bir asosiy o‘yin boshqasini boshlatmaydi; zar dueli alohida ishlashi mumkin.

## 6. Krokodil va Haqiqat yoki jasorat (5, 6)

- [ ] `/krokodil` da faqat boshlovchi “So‘zni ko‘rish” ni bossin, C ham urinsin.
  **Natija:** so‘z faqat boshlovchining popupida; C ko‘ra olmaydi.
- [ ] Boshlovchi ikki marta tashlasin, uchinchi marta urinsin. B so‘zni lotin/kirill yoki apostrof variantida topsin.
  **Natija:** faqat ikki tashlash; mos variantlar qabul qilinadi. B +5, boshlovchi +3, B keyingi boshlovchi.
- [ ] Boshlovchi so‘zni chatda yozsin; keyingi raundda 3 daqiqa kuting.
  **Natija:** so‘zni oshkor qilgan −3 va yangi so‘z; timeout so‘zni ochib rozilikdagi yangi boshlovchi tanlaydi.
  10 raund yoki /stop o‘yinni yakunlaydi.
- [ ] B xabariga reply qilib `/hyj` yuboring; A/C tanlov tugmalarini bossin.
  **Natija:** faqat B Haqiqat/Jasorat/Rad etishni tanlaydi; reply bo‘lmasa tasodifiy rozilikdagi a’zo.
- [ ] Haqiqatga matn va alohida o‘yinda ovoz bilan javob bering.
  **Natija:** 30 daqiqalik muddatda javob +5, takror javob ortiqcha ball bermaydi.
- [ ] Jasoratni bajaring; keyingi o‘yinda rad eting, yana birida vaqtini o‘tkazing.
  **Natija:** bir soatlik vazifa odatdagi tur ballini beradi; rad etish faqat −2,
  mute/kick yo‘q. O‘tkazilgan jasorat odatdagi tanlangan vazifa jarimasiga bo‘ysunadi.
- [ ] `/stop` va maqsadli odamning `/chiqish` ini sinang.
  **Natija:** bog‘liq vazifa/o‘yin bekor, bekor qilish uchun yangi jarima yo‘q.

## 7. Mafia va kengaytirilgan rollar (7, 12)

- [ ] Uchlikda `/mafia`, havola orqali shaxsiy Start va qayta bosishni sinang; 90 soniya kuting.
  **Natija:** bitta tahrirlanadigan lobby, faqat deep link orqali kirish, 5 dan kamligi uchun bekor.
  Bitta foydalanuvchi bir payt ikki Mafia lobby/o‘yiniga kirmaydi.
- [ ] Sozlamada kengaytirilgan rollar va o‘lganlarning xabarini o‘chirish dastlab OFF bo‘lsin.
  **Natija:** A o‘zgartira oladi, B/C yo‘q; yangi rol sozlamasi keyingi lobbyga ta’sir qiladi.

**Quyidagi qadamlar uchun qo‘shimcha haqiqiy qatnashuvchilar kerak. Yetarli bo‘lmasa ochiq qoldiring.**

- [ ] 5+ a’zo bilan butun oddiy Mafia o‘ynang. 6 kishidan biri rol oldidan botni bloklasin.
  **Natija:** rol DM yetmagan odam oldindan chiqarilib, rollar qayta hisoblanadi; 5 qolsa davom, 4 qolsa bekor.
- [ ] Tunda mafia/doktor/komissar, kunduzi muhokama va ovozni sinang.
  **Natija:** tun 60, muhokama 90, ovoz 60 soniya. Mafia sheriklari/ismlari va jonli hisobi faqat
  mafiyaga; ovoz bermasa hujum yo‘q. Doktor o‘zini ketma-ket saqlamaydi, komissar bir tekshiruv qiladi.
  Teng mafia ovozi tasodifiy, teng kunduzgi ovozda hech kim chiqmaydi.
- [ ] O‘lgan odam, boshqa odamning shaxsiy tugmasi va eski raund tugmasini sinang.
  **Natija:** rad etiladi. Tongda qurbonning roli ochiladi. O‘lik xabarini o‘chirish faqat yoqilgan va delete huquqi borida ishlaydi.
- [ ] Oddiy tinch/mafia g‘alabasini, /stop va restartni sinang.
  **Natija:** g‘olib tomonga +10, tirik qolganlarga +3; forfeit bo‘lganlarga yo‘q.
  20 raund/60 daqiqada durang; durangda faqat tiriklik balli. Stop/restart bekor va shaxsiy xabar beradi.
- [ ] 8+ kishi, extended ON: Don ovoz tengligini hal qilsin, komissar uni tekshirsin.
  **Natija:** Don mafia tomonida, komissarga tinch ko‘rinadi; mafia soni ortib ketmaydi.
- [ ] 9+ kishi: Ma’shuqa bir harakatni to‘ssin, o‘sha odamni keyingi tun tanlasin.
  **Natija:** to‘silgan harakat bajarilmaydi; bir xil nishon ketma-ket taqiqlangan.
  Komissar natijasi tongda shaxsiy, to‘silganda natija yo‘q. Doktor o‘lsa ham saqlashi ishlaydi.
- [ ] 11+ kishi: Manyak va mafia ikki nishonga hujum qilsin; doktor bittasini saqlasin.
  **Natija:** ikki hujum bir vaqtda, bir saqlangan nishon har ikkala hujumdan himoyalangan.
  Manyak tirik va ko‘pi bilan bitta boshqa odam qolsa yutadi; town uchun mafia ham Manyak ham yo‘q,
  mafia uchun Manyak yo‘q va mafia qolganlardan kam emas bo‘lishi kerak.

## 8. Haftalik xulosa va rasmli natijalar (8, 9)

- [ ] Haftada ball oling, yakshanba mahalliy 20:00–21:00 ni kuting.
  **Natija:** bitta xulosa: top 5, eng faol (ball keltirgan alohida ishtiroklar), vazifa hisoblari,
  shior/muallif/qo‘shish tugmasi. Xom xabar ko‘pligi eng faol degani emas.
- [ ] Xulosadan so‘ng restart qiling; alohida haftada tinch vaqtni dushanbagacha suring.
  **Natija:** tasdiqlangan xulosa takrorlanmaydi; dushanbaga surilgani o‘tgan haftaga tegishli.
- [ ] `RESULT_CARDS_ENABLED=true` bilan g‘olibli o‘yin va haftalik xulosani tekshiring.
  **Natija:** matnli natija hamda bitta o‘zbek harfli, uzun ism sig‘adigan, Instagram belgili rasm.
  Bekor qilingan/g‘olibsiz o‘yinda noto‘g‘ri g‘olib kartasi chiqmaydi.
- [ ] Kartalarni o‘chirib restart qiling, yangi o‘yin o‘ynang.
  **Natija:** matn va ball ishlaydi, yangi rasm yo‘q; oxirida kerakli sozlamani qaytaring.

## 9. Egaga vositalar, maxfiylik va tiklanish (10)

- [ ] A shaxsiy `/stats` yuborsin, B ham, A guruhda ham urinsin.
  **Natija:** faqat OWNER_ID shaxsiy chatda guruh/a’zo/24 soat faollik/7 kun o‘yinlar/navbat/tick ma’lumotini ko‘radi.
- [ ] `/maxfiylik` ni o‘qing. B shaxsiy `/malumotlarimni_ochir` ni yuborsin, boshqa odam uning tugmasini sinasin.
  **Natija:** sodda tushuntirish, faqat so‘rov egasining tasdig‘i ishlaydi; muddati o‘tgan/takror tasdiq ishlamaydi.
- [ ] B ball olgan va o‘yinda bo‘lgan hisobini tasdiqli o‘chirsin.
  **Natija:** uning roziligi/shaxsiy jonli ma’lumotlari/ballari tozalanadi, tegishli o‘yin bekor;
  boshqalarning ballari saqlanadi. Allaqachon Telegramga ketgan xabar va operator backupi o‘chirilgan deb aytilmaydi.
- [ ] B eski tugma/xabarni sinasin; keyin `/start`, yangi `/qoshilish` qilsin.
  **Natija:** eski ish ma’lumotni tiklamaydi; yangi rozilik bilan yangi ma’lumot yaratilishi mumkin, eski ball qaytmaydi.
- [ ] Ctrl+C bilan to‘xtating va qayta yoqing; tiklash testlarini pastdagi buyruq bilan bajaring.
  **Natija:** faoliyat buferi tozalanadi, navbatga ko‘pi bilan 10 soniya beriladi.
  Muhim e’lon 6 soat ichida tiklanishi mumkin, ball qayta yozilmaydi; eskisi skip qilinadi.
  Xotiradagi oddiy kuzatuvlar/past navbat/o‘yin ta’sirlari crashda yo‘qolishi qabul qilingan.

## 10. Mavsum, seriya va yutuqlar (11)

- [ ] `/top`, `/yutuqlar` ni tekshiring; ilk video/vazifa, Krokodil 10 topish va Mafia g‘alabasini bajaring.
  **Natija:** joriy mahalliy kalendar oy + barcha vaqt; tegishli yutuq bir marta ochiladi,
  yutuqning o‘zi yana ball bermaydi; qisqa xabarlar to‘planib keladi. Mafia g‘alabasi uchun 5+ kerak.
- [ ] Har kun kunlik postdan keyin qatnashing, 7 va 30 kunlik seriyani kuzating.
  **Natija:** odatdagi +1 yoniga 7-kuni +3, 30-kuni +10. 14/60-kun qayta bonus emas;
  kun qoldirilsa seriya yangidan, oy almashishi uzmaydi. Uzoq sinov o‘tmaguncha belgilamang.
- [ ] Oyning 1-kuni mahalliy 09:00–09:15 yoki tinch vaqt tugashini kuting.
  **Natija:** oldingi oy chempionlari, saqlangan ledger; oy kelganda ballar nolga tushmaydi.
  Restart takror mukofot bermaydi. Tez test uchun avtomatik suite; real kompyuter soatini o‘zgartirmang.

## 11. Mini App (13; o‘z HTTPS domeni kerak)

- [ ] README bo‘yicha o‘z domeni va BotFather Main Mini App ni sozlang.
  **Natija:** `WEBAPP_URL=https://sizning-domeningiz/webapp`; oddiy brauzerda profil so‘ralsa Telegram ichidan ochish talab etiladi.
- [ ] Shaxsiy /start yoki /help dagi ilovani, guruh /help dagi havolani oching.
  **Natija:** shaxsiy web_app tugma va guruh Main Mini App havolasi ishlaydi; kerakli guruh tanlanadi.
- [ ] Profil, mavsum/barcha vaqt reytingi, o‘z yutuqlari, qoidalar, yorug‘/qorong‘i mavzuni tekshiring.
  **Natija:** ismlar oddiy matn, sahifa ko‘rish rozilik/ballni o‘zgartirmaydi; Mafia roli ko‘rinmaydi.
- [ ] B guruhdan chiqib sahifani yangilasin; 24 soatdan keyin ilovani qayta ochsin.
  **Natija:** joriy a’zolik yo‘q bo‘lsa guruh sahifasi rad etiladi; eskirgan tasdiq qayta ochishni so‘raydi.
  Havoladagi boshqa user/chat ID ruxsat bermaydi. initData/tokenni hech kimga yubormang.

## 12. Kontent va texnik tekshiruvlar (0.5, 14)

- [ ] `python scripts/validate_content.py` bajaring, CONTENT_GUIDE.md ni o‘qing.
  **Natija:** olti bankda 3 tadan namuna va [OK]. Bu hali katta, tekshirilgan kontent banki emas.
- [ ] Olti JSON ni `build/content-test` kabi alohida sinov nusxasiga oling. Takror key,
  apostrof/kirill bilan bir xil matn, uzun matn, xato variant/javob, buzilgan JSON qo‘ying.
  `python scripts/validate_content.py --directory build/content-test` bilan tekshiring.
  **Natija:** kod 1 va tushunarli xato; tuzatsa 0. [] bank 0 ta bilan o‘tadi, yo‘q fayl xato.
- [ ] Quyidagilarni virtual muhitda bajaring:

  ```powershell
  python -m pytest -q
  ruff check .
  alembic check
  python scripts/simulate_load.py --ticks 10
  ```

  **Natija:** testlar/lint/sxema o‘tadi; 5 000 soxta guruhda har turga tick ko‘pi bilan 500,
  o‘n tickda 15 000 due ish. Haqiqiy Telegram so‘rovi yo‘q; bu 10 000 guruh quvvati isboti emas.
- [ ] Maqsadli suite’larni bajaring: `python -m pytest tests/test_hardening.py tests/test_claude_review.py tests/test_seasons_achievements.py tests/test_mafia_engine.py tests/test_mafia_extended.py -q`.
  **Natija:** crash/6 soat/no-double-points, alohida deadlines, migration/backoff/anonim admin,
  oy/seriya va oddiy/kengaytirilgan Mafia fuzz testlari o‘tadi. Jonli tekshirilmagan qadamlar baribir ochiq qoladi.
- [ ] A alohida sinov guruhini superguruhga o‘tkazsin (Telegramda shunday amal mavjud bo‘lsa).
  **Natija:** yangi IDga a’zolik/ball/vazifalar ko‘chadi, eski guruh nofaol; RPS/son/matematika bekor.
  Mijoz bu amalni taklif qilmasa jonli sinov bajarilmadi deb yozing, avtomatik test bilan aralashtirmang.

## 13. Ishlab chiqarish vositalari (17; alohida sinov muhiti)

- [ ] README bo‘yicha Docker/PostgreSQL va ixtiyoriy Caddy HTTPS yo‘lini tekshiring.
  **Natija:** faqat shu loyiha xizmatlari, .env obraz/Git ichida yo‘q; haqiqiy domenni egasi sozlaydi.
- [ ] HTTP rejimida `/healthz` ni oching.
  **Natija:** yangi tick bilan 200 va navbat/age; birinchi tick yo‘q yoki 120 soniyadan eski bo‘lsa 503.
  Docker healthcheck ham shu manzilni tekshiradi. Unhealthy avtomatik restart degani emas.
- [ ] A botga shaxsiy Start yuborgan bo‘lsin; xato alertlari testini `python -m pytest tests/test_production.py -q` bilan bajaring.
  **Natija:** faqat xavfsiz xulosa, 10 daqiqada ko‘pi bilan bitta, qo‘shilgan xatolar soni;
  alertning o‘zi ishlamasa bot buzilmaydi. Jonli xato yaratish uchun bazani buzib qo‘ymang.
- [ ] README bo‘yicha backup va yangi bo‘sh bazaga restore qiling.
  **Natija:** kundalik custom dump, 14 kun saqlash, yangi bazada tekshiruv; ishlab turgan baza o‘zgarmaydi.

## 14. Yangi o‘yinlarga umumiy rozilik va himoya (18–21)

- [ ] Botga xabarlarni o‘chirish huquqini bering, A/B/C /qoshilish qilsin.
  **Natija:** /telefon va /eslaysizmi shu huquqsiz boshlanmaydi; sinov uchun zararsiz surat/ovoz tanlanadi.
- [ ] /oyinlar, guruhdagi va shaxsiy /help, Mini App qoidalarini oching.
  **Natija:** /yashirin, /fosh, /kimaytdi, /telefon, /eslaysizmi bor; ishtirokchi soni va nima ochilishi tushunarli.
- [ ] Lobby matnini o‘qing va uning shaxsiy havolasini bosib Start qiling.
  **Natija:** lobbyda guruhga nima chiqarilishi aytilgan; faqat shu havoladan rozilik bilan qo‘shilasiz.
- [ ] Bitta shaxsiy o‘yinda qatnashib turib boshqasining havolasini bosing (Mafia ham kiradi).
  **Natija:** shaxsiy chatda bandlik tushuntiriladi, ikkinchi o‘yinga kirmaysiz. Birinchi tugagach qo‘shilish mumkin.
- [ ] Shaxsiy topshiriqqa havola, @eslatma, uzatilgan xabar yoki talabga mos bo‘lmagan media yuboring.
  **Natija:** rad etiladi, ball berilmaydi. To‘g‘ri yangi javob qabul qilinadi; takroriy javob materialni almashtirmaydi.
- [ ] Guruhdagi foydalanuvchi materialida oddiy B yashirish tugmasini bossin, so‘ng admin A bossin.
  **Natija:** B yashira olmaydi. A materialni o‘chiradi yoki matnda yashirish belgisi chiqadi; muallifning shu material bali yo‘q.
- [ ] O‘yin tugagach bonusli materialni yashiring va qayta bosing.
  **Natija:** bonus bir marta bekor bo‘ladi, /top va yakuniy jadval yangilanadi. Boshqa odamning topish bali bekor bo‘lmaydi.
- [ ] Faqat sinovda, media chiqarilgach botning o‘chirish huquqini olib, admin yashirishni bossin; keyin huquqni tiklang.
  **Natija:** izoh belgilanishi surat/ovozni o‘chirmaydi; bot bu cheklovni aniq aytadi. Admin mediani qo‘lda o‘chirsin.
  Telegram o‘chirishni boshqa sabab bilan rad etsa ham qo‘lda tekshiring; belgini to‘liq o‘chirish deb hisoblamang.
- [ ] Har yangi o‘yinda alohida /stop, /chiqish, qayta yoqish va /malumotlarimni_ochir tasdig‘ini sinang.
  **Natija:** faol o‘yin bekor bo‘ladi, shaxsiy joy bo‘shaydi, kechikkan material chiqmaydi; oldin yozilgan ball takrorlanmaydi.
  Ma’lumotni o‘chirish fayl identifikatori/izohni ham tozalaydi; yetkazilgan Telegram xabarlari va tashqi backup alohida.
- [ ] Eski raund, boshqa o‘yin va migratsiyadan oldingi tugmalarni sinang.
  **Natija:** eski taxmin ishlamaydi; eski guruhdagi material ID si yangi guruhning boshqa xabarini o‘chirmaydi.
  Migratsiyadan qolgan material kerak bo‘lsa admin qo‘lda o‘chiradi. Xavfli migratsiyani asosiy guruhda majburlamang.

## 15. Yashirin topshiriq — A/B/C bilan (18)

- [ ] CONTENT_GUIDE bo‘yicha secret_words.json ga kamida 4 turli so‘z qo‘ying, validatorni ishga tushiring.
  **Natija:** bank to‘g‘ri. Faqat 3 namuna qolsa uch kishilik o‘yin yetishmaslikni aytib bekor bo‘ladi.
- [ ] A /yashirin yuborsin, 2 soatni tanlasin; B boshqa muddatni bosib ko‘rsin, uchlik shaxsiy havoladan qo‘shilsin.
  **Natija:** muddatni faqat A o‘zgartiradi; odatiy muddat 24 soat, boshqa tanlov 6 soat; lobby 5 daqiqa.
- [ ] Lobbydan keyin har kim o‘z nishoni va maxfiy so‘zini shaxsiy ko‘rsin.
  **Natija:** har kim bitta odamni ovlaydi va bitta odam uni ovlaydi; faol so‘zlar takrorlanmaydi.
- [ ] Nishon so‘zni guruhga yangi matn/rasm izohida yozsin; palov so‘zi bo‘lsa palovni/palovdan ni ham sinang.
  **Natija:** ovchi +10, so‘z guruhda ochiladi va yangi so‘z keladi; 3 muvaffaqiyatdan keyin yangi topshiriq berilmaydi.
- [ ] So‘zli eski xabarni uzating yoki tahrirlang; aloqasiz oddiy xabar ham yozing.
  **Natija:** ular uchun yutuq yo‘q. Apostrof/kirill bir xil so‘z sifatida taniladi; qisqa so‘z faqat to‘liq token bilan moslashadi.
- [ ] /fosh ni haqiqiy ovchining xabariga javoban, keyin alohida holatda noto‘g‘ri gumon bilan yuboring.
  **Natija:** to‘g‘ri +5, so‘z ochilib yangilanadi; xato −2 va 1 soat kutish. Jami 3 gumondan oshmaydi.
- [ ] Yashirin davomida /sontop yoki boshqa asosiy o‘yinni boshlang; fon doskasiga /stop bilan javob bering.
  **Natija:** asosiy joy alohida; javobli /stop faqat fon o‘yinini to‘xtatadi. Oddiy /stop asosiy o‘yinni tanlaydi.
- [ ] To‘rt odam bilan boshlang, bittasi /chiqish qilsin; so‘ng ikkinchisi ham chiqsin.
  **Natija:** uchlikda nishonlar tuzatiladi, ikki kishi qolganda bekor bo‘ladi. Tabiiy 2/6/24 soat oxirida natija jadvali chiqadi.

## 16. Kim aytdi? — A/B/C/D bilan (19)

- [ ] To‘rtinchi odam D /qoshilish qilsin; /kimaytdi va shaxsiy havolalar orqali kiring.
  **Natija:** lobby 3 daqiqa, 4–12 kishi; uch odam qolsa to‘liq o‘yin boshlanmaydi.
- [ ] Har kim bir xil shaxsiy savolga 5 daqiqada bitta 1–300 belgili matn yuborsin.
  **Natija:** erta javob ham qabul qilinadi; ikkinchi javob, 301 belgi, link, ovoz va surat rad etiladi.
- [ ] Guruhda javoblarni birma-bir ko‘ring, nomli tugmalardan taxmin tanlang.
  **Natija:** tartib tasodifiy, muallif avval yashirin. Muallif o‘z javobiga ovoz bera olmaydi, har odam bir marta tanlaydi.
- [ ] Bir raundda ikki odam to‘g‘ri topsin, boshqasida hech kim topmasin.
  **Natija:** 30 soniyadan keyin o‘sha xabar tahrirlanib muallif ochiladi; to‘g‘ri topganlarning har biri +3,
  hech kim topmagan javob muallifi +3. Eski tugma qo‘shimcha ball bermaydi.
- [ ] Bir o‘yinda hech kim javob yubormasin, boshqasida faqat ayrimlar javob bersin.
  **Natija:** 5 daqiqada javobsiz o‘yin bekor; qisman javoblar bilan kelgan materiallar o‘ynaladi, qolganlar ham taxmin qiladi.

## 17. Ovozli buzilgan telefon — A/B/C/D bilan (20)

- [ ] /telefon ni boshlang, to‘rtlik havoladan kirsin; lobbydan keyin birinchi ovozli topshiriqni kuting.
  **Natija:** lobby 3 daqiqa, 4–10 kishi, navbat tasodifiy; birinchi odamga matnli jumla keladi.
- [ ] Birinchi odam yangi ovoz yuborsin, keyingi odamlar eshitib o‘z ovozida qaytarsin.
  **Natija:** navbat 2 daqiqa, ovoz ko‘pi bilan 30 soniya. Keyingiga faqat oxirgi ovoz, asl jumla yoki oldingi ism kelmaydi.
- [ ] Navbati kelmagan odam, 31 soniyalik/uzatilgan ovoz va oddiy audio fayl bilan urinib ko‘ring.
  **Natija:** qabul qilinmaydi; yangi Telegram voice xabari kerak. Oxirgi odam ovoz o‘rniga eshitganini matn yozadi.
- [ ] O‘rtadagi odam javob bermasin; keyin alohida o‘yinda oxirgi odam matn yozmasin.
  **Natija:** kechikkan odam o‘tkaziladi va oxirgi yaxshi ovoz keyingiga o‘tadi; yakuniy matn yo‘q bo‘lsa aniq aytiladi.
  Hali ovoz bo‘lmasa keyingi so‘zlovchiga asl jumla beriladi; hech kim topshirmasa o‘yin bekor.
- [ ] Zanjirni oxirigacha tugating va guruhdagi natijani tinglang.
  **Natija:** asl jumla, yakuniy matn, keyin ovozlar navbat bilan chiqadi. Har materialda hide tugmasi,
  yashirilmagan material topshirgan har odamga +3; to‘rt topshiruvchi uchun +12 bir marta.

## 18. Eslaysizmi? — A/B/C bilan (21)

- [ ] /eslaysizmi yuboring, uchlik havoladan qo‘shilsin va rozilikni o‘qisin.
  **Natija:** lobby 5 daqiqa, 3–10 kishi; surat guruhga chiqishi va izoh keyin ochilishi aniq.
- [ ] Har kim 5 daqiqada bittadan oddiy sinov surati yuborsin; ixtiyoriy qachon/qayerda izoh qo‘shing.
  **Natija:** yangi photo qabul qilinadi; hujjat qilib yuborilgan rasm, ovoz, matn, link/@eslatmali izoh,
  uzatilgan surat, 301 belgili izoh va ikkinchi surat rad etiladi.
- [ ] Suratlarni guruhda kuzating va tugmalardan taxmin tanlang.
  **Natija:** har surat bir marta spoiler bilan chiqadi; izoh va yuboruvchi avval ochilmaydi.
  Har odam bir taxmin qiladi; o‘z suratiga ovoz berib bepul ball olib bo‘lmaydi.
- [ ] Bir suratni ikki kishi to‘g‘ri topsin; boshqa suratda hech kim topmasin.
  **Natija:** 30 soniyadan keyin o‘sha suratning izohi tahrirlanadi, yuboruvchi va yashirin izoh ochiladi;
  surat qayta yuborilmaydi. Har topuvchiga +3, kamida bir topuvchi bo‘lsa yuboruvchiga +2; hech kim topmasa yuboruvchiga 0.
- [ ] Admin suratni raundda yoki bonus berilgach yashirsin.
  **Natija:** yashirilgan surat/izoh qayta ochilmaydi, yuboruvchining shu +2 bonusi yo‘q yoki bir marta qaytariladi;
  to‘g‘ri topuvchilarning boshqa ballari saqlanadi. Huquq yo‘qolsa rasmni admin qo‘lda o‘chirsin.
- [ ] Hech kim surat yubormaydigan va faqat bittasi yuboradigan o‘yinlarni sinang.
  **Natija:** javobsiz o‘yin bekor; kelgan bitta surat bilan bitta raund o‘ynaladi, keyin shaxsiy joylar bo‘shaydi.
- [ ] Suratlar hali chiqarilmasidan /malumotlarimni_ochir ni tasdiqlang va boshqa o‘yinda botni qayta yoqing.
  **Natija:** o‘yin bekor, fayl identifikatori/izoh o‘chiriladi yoki restartda yangi topshiriq talab qilinadi;
  kechikkan surat yuborilmaydi, eski tugmalar ishlamaydi. Avval yetkazilgan Telegram suratlari avtomatik o‘chmaydi.

## 19. Xato bo‘lsa jurnalni qanday topish

- [ ] Muammo vaqtini va qadam raqamini yozing, so‘ng tegishli satrlarni toping:

  ```powershell
  Get-Content .\bot-live.log -Tail 100
  Select-String -Path .\bot-live.log -Pattern 'ERROR|Traceback|retry_after|queue_length|last_tick'
  docker compose -p oqibat logs --tail 100 bot
  docker compose -p oqibat logs --tail 30 backups
  ```

  **Natija:** mahalliy yoki Docker yo‘lidan foydalanganingizni ajratasiz.
  `Unhandled error processing update` — update xatosi; `Scheduled ... failed` — jadval ishi;
  `Telegram operation failed` — yuborish; `backing off` — 10 daqiqa tanaffus;
  `retry_after` — Telegram so‘ragan kutish. Har besh daqiqada navbat/faollik/tick chiqadi.
- [ ] Xulosa kelmasa vaqt mintaqasi, tinch vaqt, kunlik offset, eski tasdiqlangan post va bot adminligini tekshiring.
  **Natija:** tabiiy kutish bilan xato farqlanadi. Yetkazilganiga javob yo‘qolsa e’lon takror bo‘lishi mumkin,
  ammo ball takrorlanmasligi kerak; 6 soatdan eskisi tiklanmaydi.
- [ ] Claude ga faqat commit, qadam, vaqt, kutilgan/haqiqiy natija va maxfiy qiymatlarsiz jurnal parchasini bering.
  **Natija:** token, parol, WEBHOOK_SECRET, initData, .env va keraksiz shaxsiy matn yuborilmaydi.
  Avval parchani o‘zingiz ko‘zdan kechiring; bot redaksiyasiga ko‘r-ko‘rona ishonmang.
- [ ] Testdan keyin ism/huquq/cheklov/sozlamalarni tiklang, ochiq o‘yinlarni tugating.
  **Natija:** ishchi nusxa tartibli, asl namunalar qaytarilgan. `git status --short` va
  `git rev-parse --short HEAD` ni qayd qiling. Claude repodan klonlaydi, ZIP kerak emas.

```text
Sana/vaqt (Asia/Tashkent):
Commit:
Sinov bot username (token emas):
A / B / C (Kim/Telefon uchun D; Mafia uchun qo‘shimcha odamlar):
O‘tgan qadamlar:
Ishlamagan qadam va kutilgan/haqiqiy natija:
Jurnal vaqti / update raqami:
Bajarilmagan uzoq, Mafia yoki HTTPS sinovlari va sababi:
```
