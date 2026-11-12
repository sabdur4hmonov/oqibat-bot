# Oqibat uchun matn yozish

Hozir har bankda uchta namuna bor. Katta, tayyor bankni Sardorbek va Claude yozadi.
Bu qo‘llanma matn shaklini tekshiradi; mazmunning to‘g‘riligi va odobliligini odam tekshiradi.
Botni ishlatmay turib ham banklarni tekshirish mumkin: token, .env yoki baza kerak emas.

## Avval shu qoidalar

- `data` ichida pastdagi olti `.json` fayl bo‘lsin. Boshqa nomli JSON bu bankka kirmaydi.
- Har fayl `[` bilan boshlanadigan ro‘yxat. Bo‘sh bank `[]` bo‘lishi mumkin; tegishli
  imkoniyat mazmun topilmaguncha ishlamaydi. Faylni o‘chirib tashlamang.
- Har elementning `key` qiymati butun loyihada noyob, 1–128 belgi bo‘lsin.
  `daily_004`, `challenge_004`, `quiz_004`, `word_004`, `wyr_004`, `truth_004`
  kabi old qo‘shimcha tavsiya qilinadi. `id` emas, aynan `key` yozing.
- Eski key ni boshqa mazmun uchun qayta ishlatmang. Bot qaysi matn ishlatilganini
  va vazifa qaysi matndan olinganini shu qiymat bilan eslaydi. Tuzatish kichik bo‘lsin;
  butunlay yangi savolga yangi key bering.
- Matn o‘zbek lotinida, oddiy matn bo‘lsin. HTML teg yozmang: bot ularni oddiy matn
  qilib ko‘rsatadi. Muallif havolasi yoki reklama qo‘shmang; bot kerakli joyda o‘zi qo‘shadi.
- Faqat kunlik matnda `{group}` bir marta bo‘lishi mumkin. Boshqa `{name}` yoki
  shunga o‘xshash o‘rinbosar ishlamaydi. Guruh nomini bot o‘zi xavfsiz qo‘yadi.
- Bir bankda bir xil asosiy matn takrorlanmasin. Tekshiruv katta-kichik harfni,
  apostrof/bo‘sh joy/tinish belgisini birlashtiradi va o‘zbek kirillini lotinga o‘giradi.
  `O‘zbekiston`, `Oʻzbekiston`, `Ўзбекистон`, `Ozbekiston` bir xil hisoblanadi.
  Asosiy matn — `text`, `question` yoki `word`. Variantlarni almashtirish bir xil
  savolni yangi savol qilib qo‘ymaydi. Variantlar ham o‘z ichida takrorlanmasin.
- Qisqa, tushunarli, do‘stona yozing. Xavfli, sharmanda qiladigan yoki shaxsiy sirni
  so‘raydigan vazifa bermang. Javob/rasm/ovoz berish ixtiyoriy ekanini unutmang.

## Uzunliklar

Belgi soniga bo‘sh joy va tinish belgilari ham kiradi. Bu bayt soni emas.
2 000 belgilik chegara botning ism, guruh nomi va muddat kabi qo‘shimchalariga joy qoldiradi.

| Maydon | Ruxsat |
| --- | --- |
| Har qanday `key` | 1–128 belgi, barcha banklarda noyob |
| Kunlik/vazifa/haqiqat `text` | 1–2 000 belgi, faqat bo‘sh joy emas |
| Viktorina yoki tanlov `question` | 1–300 belgi |
| Har bir `options` varianti | 1–100 belgi, farqli va faqat bo‘sh joy emas |
| Krokodil `word` | 1–100 belgi, topish mumkin bo‘lgan so‘z/ibora |
| Viktorina `options` soni | 2–10 |
| Tanlov `options` soni | Aynan 2 |

## Fayllar va namunalar

Quyidagi namunalar mavjud uchliklardan olingan. Kerakli maydonlardan ortiq maydon
yozmang; hatto bitta obyekt ichida `key` ikki marta yozilishi ham xato.

### data/daily_messages.json

```json
[
  {"key": "daily_001", "text": "Assalomu alaykum, {group}! Bugun kayfiyatingiz qanday?"}
]
```

### data/challenges.json

`kind` faqat `video_note` (davra videosi), `voice` (ovoz), `photo` (rasm) yoki
`text` bo‘ladi. Oddiy uzun video `video_note` o‘rnini bosmaydi. Qanday javob kerakligini aniq yozing.

```json
[
  {"key": "challenge_001", "kind": "video_note", "text": "Do‘stlaringizga qisqa video salom yo‘llang."}
]
```

### data/quiz_questions.json

`correct_option_id` noldan sanaladigan **butun son**: birinchi variant `0`, ikkinchi
`1`, uchinchi `2`. Uni qo‘shtirnoqqa olmang; `true` ham son emas. To‘g‘ri javobni
ishonchli manbadan tekshiring, bahsli yoki tez o‘zgaradigan savolni ishlatmang.

```json
[
  {
    "key": "quiz_001",
    "question": "O‘zbekiston poytaxti qaysi shahar?",
    "options": ["Toshkent", "Buxoro", "Nukus"],
    "correct_option_id": 0
  }
]
```

### data/krokodil_words.json

So‘z yoki qisqa ibora yozing. Faqat belgi/emoji topiladigan so‘z bo‘la olmaydi.
Topuvchi apostrof yoki kirill bilan yozsa ham normalizatsiya birlashtiradi.

```json
[
  {"key": "word_001", "word": "O‘zbekiston"}
]
```

### data/would_you_rather.json

Faqat ikki farqli tanlov, to‘g‘ri javob maydoni yo‘q.

```json
[
  {"key": "wyr_001", "question": "Qaysi sayohatni tanlaysiz?", "options": ["Tog‘", "Dengiz"]}
]
```

### data/truth_questions.json

Savol oddiy matn yoki ovoz bilan javob berishga qulay bo‘lsin.

```json
[
  {"key": "truth_001", "text": "Bolalikdagi eng yoqimli xotirangiz qaysi?"}
]
```

## Saqlash va tekshirish (Windows PowerShell)

Faylni UTF-8 **BOMsiz** saqlang. JSON kaliti va matni atrofida oddiy `"` kerak;
matn ichidagi qo‘shtirnoq `\"`, yangi qator `\n` bo‘ladi. Oxirgi elementdan keyin
vergul yoki `// izoh` qo‘ymang. Apostrof uchun `‘`/`ʻ` ishlatish mumkin.
Eski Windows PowerShell 5 dagi `Set-Content -Encoding UTF8` BOM qo‘shishi mumkin;
zamonaviy muharrirning “UTF-8” saqlashini ishlating.

Loyiha papkasida, virtual muhit yoqilgach:

```powershell
python scripts/validate_content.py
$LASTEXITCODE
```

Har fayl uchun element soni chiqadi. `0` — tekshiruv o‘tdi, `1` — xato bor.
Xatoda fayl nomini, ko‘rsatilsa element tartibini ko‘ring (bu tartib **1 dan** sanaladi).
`schema` xabarida jadval/maydonlarni, takroriy key va uzunliklarni tekshiring;
`? ta element` fayl hali o‘qilmagani yoki ro‘yxat shaklida emasligini bildiradi.
Bir bankning tuzilishi buzilgan bo‘lsa, avval uni tuzating va yana tekshiring —
keyingi mazmun xatolari shundan keyin chiqishi mumkin.

Almashtirishdan oldin boshqa papkadagi bankni ham tekshirish mumkin:

```powershell
python scripts/validate_content.py --directory 'D:\Mening matnlarim\data'
```

Bu papkada ham barcha olti fayl bo‘lsin. Tekshiruv fayllarni o‘zgartirmaydi va
Telegramga hech narsa yubormaydi. O‘tgach Claude bilan mazmunni ko‘rib chiqing,
sinov botida sinang, so‘ng botni tinch paytda qayta ishga tushiring — banklar
ishga tushishda bir marta yuklanadi. .env ni kontent bilan birga yubormang.
# Yangi shaxsiy o‘yinlar banklari

`secret_words.json`: `[{"key":"secret_palov","word":"palov"}]`.
Bitta harfli so‘z emas, bitta mazmunli so‘z yozing; bo‘shliq va raqam bo‘lmasin,
uzunligi ko‘pi bilan 32 belgi. Faol ovchilarga takrorlanmaydigan so‘z beriladi;
o‘yinni boshlash uchun o‘yinchilar sonidan kamida bitta ko‘p turli so‘z kerak.
Uchta namuna faqat formatni ko‘rsatadi: 3 kishilik sinov uchun kamida 4 ta,
20 kishilik o‘yin uchun kamida 21 ta so‘z tayyorlang.

`kim_aytdi_questions.json`: `[{"key":"kim_xotira","text":"Eng quvnoq xotirangiz nima?"}]`.
`telephone_phrases.json`: `[{"key":"telephone_bog","text":"Bog‘da qizil olma pishdi."}]`.
Har ikkala `text` ko‘pi bilan 300 belgi; shaxsiy yoki noqulay ma’lumot so‘ramang.
Har faylda uchta namuna bor. `key` barcha banklarda yagona; bir xil mazmundagi
matnni apostrof yoki kirill bilan takrorlab kiritmang. Tekshirish:
`.\.venv\Scripts\python.exe scripts/validate_content.py`.
