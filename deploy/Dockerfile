# TITAN AI bot — Linux konteyner.
# MT5'ning o'zi Wine ichida (mt5 xizmati); bu yerда faqat mt5linux KLIENTI kerak.
FROM python:3.11-slim

# matplotlib/mplfinance uchun minimal runtime kutubxonalar
RUN apt-get update && apt-get install -y --no-install-recommends \
        libfreetype6 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# MetaTrader5 (Windows-only paket) ni requirements'дан chiqarib tashlaymiz —
# Linux'да o'rnatilmaydi; uning o'rniga mt5linux ko'prigi ishlaydi.
COPY requirements.txt .
RUN grep -viE '^\s*MetaTrader5' requirements.txt > req.linux.txt \
    && pip install --no-cache-dir -r req.linux.txt

COPY . .

# Bot mt5 healthcheck (compose depends_on) orqali tayyor bo'lgach ishga tushadi.
CMD ["python", "main.py"]
