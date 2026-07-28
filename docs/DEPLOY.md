# 🚀 TITAN AI — Deployment (24/7 ishga tushirish)

Bot doimo ishlashi uchun kompyuter/server **doim yoqiq** bo'lishi va **MT5 terminali ochiq** turishi kerak. Quyida variantlar.

---

## ⚠️ Muhim texnik cheklov

`MetaTrader5` Python kutubxonasi **faqat Windows'da**, o'rnatilgan MT5 desktop terminali orqali ishlaydi. Shuning uchun:
- ✅ **Windows VPS** — to'g'ridan-to'g'ri ishlaydi (tavsiya)
- ❌ **Linux/Docker** — MT5 terminali ishlamaydi (Wine bilan murakkab)
- 🔄 **Linux + MetaApi** — mumkin, lekin `app/market` modulini MetaApi SDK'ga o'zgartirish kerak (pullik xizmat)

---

## Variant 1 — Windows VPS (tavsiya) 🌟

24/7 ishlash uchun eng oddiy yo'l. Windows VPS ijaraga oling (masalan Contabo, Vultr, AWS, Hetzner — Windows Server).

### Qadamlar

1. **Windows VPS'ga ulaning** (RDP orqali)
2. **MetaTrader 5** o'rnating va demo account'ga kiring (AutoTrading yoqing!)
3. **Python 3.11** o'rnating ([python.org](https://www.python.org/downloads/), "Add to PATH")
4. **Loyihani klonlang:**
   ```bash
   git clone https://github.com/UsmonovSardor/SBS-.git
   cd SBS-
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   copy .env.example .env
   ```
5. **`.env` ni to'ldiring** (MT5_PATH, TELEGRAM_*, GROK_API_KEY, TELEGRAM_ADMIN_IDS)
6. **Ishga tushiring:**
   ```bash
   scripts\run.bat
   ```

### 24/7 avtomatik ishlashi uchun

**A) Doimiy qayta ishga tushirish (crash bo'lsa):**
```bash
scripts\run_forever.bat
```
Bu bot to'xtasa (xato/crash) — avtomatik qayta ishga tushiradi.

**B) Windows Task Scheduler (kompyuter yoqilganda avtomatik boshlanadi):**
1. Task Scheduler'ni oching → "Create Task"
2. Trigger: "At log on" (yoki "At startup")
3. Action: `run_forever.bat` ni ko'rsating
4. "Run whether user is logged on or not" ✅

**C) NSSM (professional — Windows xizmati sifatida):**
```bash
nssm install TitanAI "C:\...\SBS-\venv\Scripts\python.exe" "C:\...\SBS-\main.py"
nssm start TitanAI
```

---

## Variant 2 — Uy kompyuteri (bepul, lekin PC doim yoqiq)

Shaxsiy kompyuterда ham ishlaydi, lekin:
- Kompyuter **o'chmasligi** kerak
- MT5 terminal **ochiq** turishi kerak
- Internet **uzilmasligi** kerak

`run_forever.bat` bilan ishga tushiring. Uyqu (sleep) rejimini o'chiring.

---

## Variant 3 — Linux VPS + MetaApi (kelajak uchun)

Agar Linux/bulutда 24/7 xohlasangiz — `app/market` modulini MetaApi ([metaapi.cloud](https://metaapi.cloud)) SDK'ga o'zgartirish kerak. MetaApi MT5 terminalни bulutда ishlatadi. Pullik (kichik bepul tier bor). Bu keyingi bosqich ishi.

---

## 📋 Deploydan oldin tekshiruv

- [ ] MT5 terminal ochiq, demo'ga kirilgan, **AutoTrading yoqilgan** (yashil)
- [ ] `.env` to'ldirilgan (barcha kalitlar)
- [ ] `python main.py` mahalliy ishlaydi
- [ ] Telegram guruhga bot admin qilib qo'shilgan
- [ ] `TRADING_MODE=demo` (real pulга o'tishdan oldin ko'p test qiling!)
- [ ] Backtest natijalarini ko'rib chiqdingiz (`scripts\backtest_run.py`)

> ⚠️ **Ogohlantirish:** real pulга o'tishdan oldin kamida bir necha hafta demo'да ishlatib, `/stats` orqali natijalarni kuzating. Strategiya hali isbotlangan foydali emas.
