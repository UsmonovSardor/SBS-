# TITAN AI — Edge validatsiya hisoboti (halol natijalar)

> **Qisqa xulosa:** TITAN AI ning SMC-fusion (ovoz berish) yondashuvi H4
> taymfrejmda **statistik ISHONCHLI edge bermaydi**. Bot texnik jihatdan to'liq
> ishlaydi (signal → grafik → Telegram, 24/7), lekin uni **foydali auto-trader**
> sifatida emas, **signal / ta'lim / tadqiqot** vositasi sifatida qarash kerak.
> **Real pulda ishlatilmasin.**

Sana: 2026-08-05. Metod: xarajatli (spread) walk-forward backtest, MT5
MetaQuotes-Demo tarixiy ma'lumoti.

## Namuna

- **12 simvol:** EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD, EURJPY,
  EURGBP, GBPJPY, XAUUSD, XAGUSD
- **Davr:** 2022-09 → 2026-08 (~4 yil), H4 taymfrejm, ~1400 savdo
- **Xarajat:** spread floor 15 punkt (realistik), har savdo R'idan chegiriladi
- **Turg'unlik:** 5 ta ketma-ket vaqt-fold (walk-forward)

## Asosiy natijalar

| Konfiguratsiya | Portfel net R | Expectancy | Musbat (simvol×fold) | Musbat simvol |
|---|---|---|---|---|
| htf_bias FAOL (eski jonli) | −69.4 R | −0.041 | 30/60 (50%) | 6/12 |
| htf_bias OFF | −33.5 R | −0.024 | 32/60 (53%) | 7/12 |
| + Volume filter | −69.4 R | −0.061 | 27/60 (45%) | 5/12 |

Confidence chegarasi sweep (selektivlik testi):

| Chegara | Portfel R | Savdo | Expectancy | PF |
|---|---|---|---|---|
| 60 | −33.5 | 1368 | −0.024 | 0.96 |
| 70 | −70.9 | 778 | −0.091 | 0.87 |
| 80 | −9.7 | 55 | −0.177 | 0.76 |

## Xulosalar

1. **Edge yo'q.** Musbat (simvol×fold) ~50% = tanga tashlash. Barcha
   konfiguratsiyalarda portfel manfiy (spread'dan keyin).
2. **Confidence bashoratli emas.** Chegarani oshirsak expectancy YOMONLASHADI —
   ya'ni yuqori "ishonch"li signallar past-ishonchlidan yaxshi emas. Voting
   mexanizmi yaxshi savdoni yomonidan ajrata olmaydi.
3. **htf_bias (MTF bias) zararli** (~36R farq) — blunt "faqat HTF-trend
   yo'nalishida savdo" filtri SMC reversal setuplariga zid. **Olib tashlandi.**
4. **Volume filter (7-bob) yordam bermadi** — off-by-default qoldirildi.
5. **Regime-adaptiv vaznlar** (39/14-bob) shu namunada statik'dan yaxshi
   chiqmadi — infratuzilma bor, `adaptive_weights=False` (default).
6. **Nuans:** gross expectancy ≈ +0.02R (SMC entrylar tasodifдан arzimas
   darajada yaxshi), lekin spread xarajati (~0.044R/savdo) uni yeydi → net
   manfiy. "Edge juda kichik, xarajatdan past."

## Nega yana strategiya qo'shish yordam bermaydi

Muammo "komponent yetishmovchiligi" emas. Voting mexanizmining o'zi savdo
natijasini bashorat qilmaydi (2-xulosa). Ko'proq ovoz (Wyckoff/Elliott/Harmonic/
ICT) = ko'proq shovqin, edge emas. Foydalilik uchun boshqa yondashuv kerak
(masalan: xarajat/RR muammosini hal qilish, yoki butunlay boshqa metodologiya).

## Reproduksiya

Ma'lumot MT5 ko'prigidan olinadi; offline baholovchi skriptlar (walk-forward,
vazn sweep, chegara sweep) tahlil davomida ishlatilgan. `Backtester` spread
modeli bilan real xarajatni hisobga oladi (`app/backtesting/backtest.py`).
