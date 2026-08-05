# 🦅 TITAN AI — Trading Bot

**MetaTrader 5 + Grok AI + Telegram** asosidagi institutsional darajadagi AI savdo boti.

Bot real-time bozorni tahlil qiladi, Smart Money Concepts (SMC/ICT) va boshqa strategiyalar asosida signal generatsiya qiladi, uni **grafik + tushuntirish** bilan Telegram kanalga yuboradi. Har signal tagida **🟢 Auto-Trade** tugmasi bo'lib, bosilganda MT5 account'da avtomatik savdo ochadi (Take Profit / Stop Loss bilan).

> ⚠️ **Ogohlantirish:** Bu dastur **ta'lim va tadqiqot** maqsadida — **signal/alert vositasi**, foydali auto-trader emas.
>
> 🔬 **Halol natija:** Keng validatsiya (12 simvol × 4 yil, walk-forward) shuni ko'rsatdiki, strategiyaning SMC-fusion yondashuvi H4'da **statistik ishonchli edge bermaydi** (natija ~tanga tashlash). Batafsil: [docs/EDGE_ANALYSIS.md](docs/EDGE_ANALYSIS.md). **Real pulda ishlatilmasin.** Bu litsenziyalangan moliyaviy maslahat emas.

---

## 🎯 Asosiy imkoniyatlar

- 📊 **Real-time MT5 ulanish** — narx va grafik ma'lumotlari
- 🧠 **Multi-Strategy Fusion** — bir nechta strategiya ovoz beradi, konsensus asosida qaror
- 🔍 **Smart Money Concepts** — BOS, CHoCH, Order Block, FVG, Liquidity Sweep
- 🤖 **Grok AI** — signalni tushuntiradi ("nimaga asoslanib?")
- 📈 **Grafik generatsiya** — entry/SL/TP chiziqlari bilan
- 📱 **Telegram** — signal + Auto-Trade tugmasi
- 🛡️ **Risk Management** — "Capital First. Stability Second. Profit Third."

---

## 🏗️ Arxitektura

```
Market Data (MT5)
      ↓
Scanner → Market Structure → Liquidity → Order Block → FVG
      ↓
AI Fusion Engine (voting + weight + confidence)
      ↓
Grok AI (tushuntirish)
      ↓
Grafik + Telegram signal
      ↓
[Auto-Trade tugmasi] → MT5 Execution (TP/SL)
      ↓
Journal → Analytics
```

## 📁 Papka tuzilishi

```
titan_ai/
├── app/
│   ├── core/          # config, logger, constants, exceptions
│   ├── market/        # MT5 connector, real-time data feed
│   ├── smc/           # bos, choch, order_block, fvg, liquidity
│   ├── strategies/    # base_strategy + har xil strategiyalar
│   ├── ai/            # fusion_engine, decision_core, grok_client
│   ├── risk/          # position sizing, stop loss / take profit
│   ├── execution/     # trade_executor, order_manager (MT5)
│   ├── charting/      # signal grafigini chizish
│   ├── telegram/      # bot, signal yuborish, tugmalar
│   └── utils/
├── config/            # sozlama fayllari
├── tests/             # testlar
├── scripts/           # yordamchi skriptlar
├── main.py            # kirish nuqtasi
├── requirements.txt
├── .env.example       # sozlama namunasi (.env ni undan yarating)
└── README.md
```

---

## 🚀 O'rnatish

```bash
# 1. Repozitoriyani klonlash
git clone https://github.com/UsmonovSardor/SBS-.git
cd SBS-

# 2. Virtual muhit
python -m venv venv
venv\Scripts\activate          # Windows

# 3. Bog'liqliklar
pip install -r requirements.txt

# 4. Sozlamalar
copy .env.example .env         # keyin .env ichini to'ldiring

# 5. Ishga tushirish
python main.py
```

### Kerakli kalitlar (`.env` ga yoziladi)
- **MT5 demo** — login, parol, server (Exness/RoboForex demo)
- **Grok API key** — https://x.ai/api
- **Telegram** — bot token (@BotFather) + kanal ID

---

## 🗺️ Yo'l xaritasi (Roadmap)

### ✅ Faza 1 — Ishlaydigan yadro (MVP) — TUGADI
- [x] Loyiha skeleti + core infratuzilma
- [x] MT5 ulanish + real-time narx
- [x] Market Structure (BOS/CHoCH) + Order Block + FVG + Liquidity
- [x] Fusion engine (voting + score + confidence)
- [x] AI (Groq) bilan signal tushuntirish
- [x] Grafik generatsiya (Entry/SL/TP + zonalar)
- [x] Telegram signal + Auto-Trade tugmasi
- [x] MT5 demo'da savdo ochish (TP/SL)
- [x] Real-time orkestrator (uzluksiz skan)

### ✅ Faza 2 — TUGADI
- [x] Admin himoyasi (/id) + Min SL sifat filtri
- [x] Pozitsiya monitoringi (break-even + trailing stop)
- [x] Trading Journal (SQLite) + /stats
- [x] Qo'shimcha strategiyalar (Momentum/EMA + ICT Kill Zones)
- [x] Backtesting engine (walk-forward)
- [x] Deploy qo'llanma (Windows VPS, [docs/DEPLOY.md](docs/DEPLOY.md))

### ✅ Faza F — Edge validatsiya (halol o'lchov) — TUGADI
- [x] Windowssiz Linux + Docker deploy (Contabo VPS, gmag11 MT5 ko'prigi)
- [x] Skaner robustligi (hang'da avto-restart + heartbeat)
- [x] HTF-aware backtester + Market Regime tizimi (39/14-bob, off-by-default)
- [x] Volume Engine (7-bob, off-by-default)
- [x] **Keng validatsiya: 12 simvol × 4 yil walk-forward** → [docs/EDGE_ANALYSIS.md](docs/EDGE_ANALYSIS.md)
- [x] **Natija: ishonchli edge YO'Q** → botni signal/ta'lim vositasi sifatida qabul qilish
- [x] `htf_bias` (zararli ~36R) olib tashlandi

### 🔮 Kelajak (agar edge qidirilsa — natija kafolatlanmagan)
- [ ] Xarajat/RR muammosini hal qilish (kattaroq RR, kam-spread filtri)
- [ ] Butunlay boshqa metodologiya (voting o'rniga) — SMC-fusion foydali chiqmadi
- [ ] ICT/Wyckoff/Elliott/Harmonic — **eslatma:** ko'proq ovoz edge yaratmaydi (EDGE_ANALYSIS.md)

---

## 📜 Litsenziya

Shaxsiy loyiha. Manba: *TITAN AI TRADING BIBLE* (45 bob + appendixlar).
