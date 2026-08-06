# TITAN AI — Bilim bazasi (Knowledge Base)

Bu papkага **strategiya, dars, fact** fayllarini tashlang. Ular signal izohларини
boyitish (ta'lim) va tahlil uchun ishlatiladi.

## Qanday qo'shish

1. Bu papkага `.md` yoki `.txt` fayl qo'shing (masalan `order-block.md`).
2. Fayl **sarlavha** (birinchi `#` qatori) + **qisqa, aniq bo'laklar**dан iborat bo'lsin.
3. Indekslash:
   ```
   python -m app.knowledge.ingest
   ```
   (Serverда: `docker exec mt5bot python -m app.knowledge.ingest`)
4. O'zgargan/yangi fayllar qayta indekslanadi, o'chirilganlar bazadан ham chiqadi.

## Yaxshi material qanday bo'ladi

- **Aniq, amaliy qoidalar** — "OB retest'да RR 1:2 dan kam bo'lса kirma" kabi.
- **Qisqa paragraflar** (2-6 gap) — semantik qidiruv aniqroq ishlaydi.
- Manba/muallifni ko'rsating (ishonchlilik uchun).

## MUHIM — halol eslatma

Bilim bazasi **signal SIFATINI o'zi o'zgartirmaydi**. U:
- ✅ Telegram izohларини chuqur, o'rgatuvchi qiladi (ta'lim).
- ✅ tahlil/kod-qoida uchun manba beradi.
- ❌ o'zi foydани (edge) YARATMAYDI — matn avtomatik savdo ustunligiga aylanmaydi.

Signal sifati faqat **kodlangan + keng namунада testдан o'tган** qoida orqali
o'zgaradi (C variant). Shuning uchun bu yerga qo'yган kuchli strategiyangizни
ayting — men uni kodlab, 12 simvol × 4 yil datада sinaб ko'raман.
