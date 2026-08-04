# TITAN AI bot — Linux konteyner.
# MT5'ning o'zi Wine ichida (mt5 xizmati); bu yerda faqat mt5linux KLIENTI kerak.
FROM python:3.11-slim

# matplotlib/mplfinance uchun minimal runtime kutubxonalar
RUN apt-get update && apt-get install -y --no-install-recommends \
        libfreetype6 libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# MetaTrader5 (Windows-only paket) ni requirements'dan chiqarib tashlaymiz —
# Linux'da o'rnatilmaydi; uning o'rniga mt5linux ko'prigi ishlaydi.
# mt5linux==0.1.9 (asl lucas-campagna klient) --no-deps bilan: uning eski
# numpy==1.21.4 pin'ini chetlab o'tamiz (bot allaqachon numpy 1.26 ishlatadi).
# Server (gmag11 mt5 konteyneri) ham 0.1.9 ishlatishi shart — deploy/mt5-init.
COPY requirements.txt .
RUN grep -viE '^\s*MetaTrader5' requirements.txt > req.linux.txt \
    && pip install --no-cache-dir -r req.linux.txt \
    && pip install --no-cache-dir --no-deps mt5linux==0.1.9

COPY . .

# Bot mt5 healthcheck (compose depends_on) orqali tayyor bo'lgach ishga tushadi.
CMD ["python", "main.py"]
