"""
TITAN AI — TradingView webhook xizmati (alohida kirish nuqtasi).

Bu ASOSIY botdan (main.py) MUSTAQIL ishlaydi — orchestrator/MT5 ishga tushmaydi.
Faqat TradingView alertlarini qabul qilib Telegram'ga uzatadi.

Ishga tushirish (lokal):
    python webhook_main.py
Yoki uvicorn bilan:
    uvicorn "app.webhook:build_app" --factory --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import uvicorn

from app.core.config import settings
from app.core.logger import log


def main() -> None:
    if not settings.tv_webhook_secret:
        log.warning(
            "⚠️  TV_WEBHOOK_SECRET .env'da yo'q — xizmat ishga tushadi, lekin "
            "HAR QANDAY so'rovni rad etadi (fail-closed). Maxfiy so'z qo'ying."
        )
    port = settings.tv_webhook_port
    log.info(f"TITAN TV Webhook ishga tushmoqda — 0.0.0.0:{port}  (POST /tv-webhook)")
    uvicorn.run(
        "app.webhook:build_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
