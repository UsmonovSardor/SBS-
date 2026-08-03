# TITAN AI — Linux VPS (Docker) Deploy Runbook

Windows'siz: Linux VPS + Docker ichida MT5 (Wine+VNC) + mt5linux ko'prigi.
Strategiya kodiga tegilmagan — faqat MT5 ulanish qatlami (`app/market/mt5_client.py`)
`MT5_HOST` env orqali nativ MT5 yoki mt5linux ko'prigini tanlaydi.

Layout: butun repo `~/mt5`ga klonlanadi, deploy `deploy/` papkasidan boshqariladi.

---

## 0. Kirish maʼlumotlari (SIZ tayyorlaysiz)
- **VPS Public IP**: `________`
- **Broker demo**: login `________`, server `________` (mas. `MetaQuotes-Demo`)
- Parol/SSH kalit/broker login/API kalit — **hammasini SIZ kiritasiz**.

---

## 1. Compute Instance (Oracle Cloud)
- Shape: **VM.Standard.E4.Flex** — 1 OCPU + 8GB RAM (x86 AMD, ARM emas)
- Image: **Ubuntu 22.04**,  Region: Frankfurt/Amsterdam,  SSH kalit: SIZ qo'yasiz

---

## 2. Portlar (Oracle IKKI joyда bloklaydi)
Bizning dizaynда tashqариga **hech qanday port ochilmaydi** — faqat SSH(22, default ochiq)
yetarli. RPyC(8001) ichki docker tarmog'ida, VNC(3000) faqat `127.0.0.1` + SSH tunnel.
Agar keyin biror port kerak bo'lsa: **(a)** OCI Console → VCN → Subnet → Security List →
Add Ingress Rule; **(b)** Ubuntu ichki firewall:
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport <PORT> -j ACCEPT
sudo netfilter-persistent save
```

---

## 3. Docker o'rnatish (Ubuntu 22.04)
```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker
```

---

## 4. Repo va sozlama
```bash
git clone https://github.com/UsmonovSardor/SBS-.git ~/mt5
cd ~/mt5/deploy
cp .env.example .env
nano .env            # broker login/parol/server + VNC parol + Groq/Telegram — SIZ kiritasiz
```

---

## 5. Botni Linux/mt5linux'ga moslash — ✅ KODда BAJARILGAN
- `app/market/mt5_client.py` — `MT5_HOST` bo'lsa mt5linux ko'prigi, bo'lmasa nativ MT5.
- `data_feed`, `mt5_connector`, `executor`: `from app.market.mt5_client import mt5`.
- `requirements.txt`: `mt5linux==1.0.11`; Docker `MetaTrader5` ni strip qiladi.
Sizga qoladigan ish: **faqat `.env`**. `MT5_HOST=mt5`, `MT5_PORT=8001` compose'дан keladi.

---

## 6. Repaint bug — ✅ TUZATILDI
`data_feed.get_candles(include_forming=False)` default: `copy_rates_from_pos(start_pos=1)`
= faqat YOPILGAN shamlar. Endi live skaner ham, backtest ham bir xil shamда ishlaydi.
Keyingi: Faza B backtestни H4 + 3 simvolда qayta yugurtirib expectancy/PF/OOS o'lchash.

---

## 7. Ishga tushirish
```bash
cd ~/mt5/deploy
docker compose up -d --build
docker compose logs -f mt5     # birinchi safar MT5 o'rnatiladi (~2-5 daq)
docker compose logs -f bot
```
Ulanишни tekshirish:
```bash
docker compose exec bot python -c "from app.market.mt5_client import mt5; print(mt5.version())"
```

---

## 8. VNC bilan MT5'ни ko'rish (login/chartlar)
Lokal kompyuterдан:
```bash
ssh -L 3000:localhost:3000 ubuntu@<VPS_IP>
```
Brauzerда: `http://localhost:3000` (VNC_USER / VNC_PASSWORD). Broker login'ini shu
yerда MT5 terminaliga qo'lда kiritasiz (agar avtomatik login qilinmasa).

---

## Xavfsizlik
- 8001 (RPyC) hech qachon internetга ochilmasin — autentifikatsiyasiz terminal boshqaruvi.
- VNC faqat SSH tunnel orqали.  •  AUTO_TRADE=false — avval signal sifatini kuzating.
- Bu DEMO — edge raqamда tasdiqlangunча real pulga o'tilmaydi.
