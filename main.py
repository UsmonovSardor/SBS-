"""
TITAN AI — Kirish nuqtasi (entry point).

Hozircha (Faza 1 boshlanishi) bu fayl faqat muhitni tekshiradi va
tizim komponentlari holatini ko'rsatadi. Keyingi qadamlarda bu yerga
to'liq savdo tsikli (scanner -> analiz -> signal -> Telegram) ulanadi.

Ishga tushirish:
    python main.py
"""
from __future__ import annotations

from app import __version__
from app.core.config import settings
from app.core.logger import log


def check_environment() -> None:
    """Sozlamalar to'ldirilganini tekshirib, holatni ko'rsatadi."""
    log.info("=" * 55)
    log.info(f"  TITAN AI  v{__version__}  ishga tushmoqda...")
    log.info("=" * 55)

    checks = {
        "MT5 login": bool(settings.mt5_login),
        "MT5 server": bool(settings.mt5_server),
        "Grok API key": bool(settings.grok_api_key),
        "Telegram token": bool(settings.telegram_bot_token),
        "Telegram kanal": bool(settings.telegram_channel_id),
    }

    for name, ok in checks.items():
        status = "✅ sozlangan" if ok else "⚠️  to'ldirilmagan (.env)"
        log.info(f"  {name:<18} {status}")

    log.info("-" * 55)
    log.info(f"  Rejim:      {settings.trading_mode.upper()}")
    log.info(f"  Simvollar:  {', '.join(settings.symbols)}")
    log.info(f"  Risk:       {settings.default_risk_percent}% / savdo")
    log.info("=" * 55)

    if settings.is_live:
        log.warning("DIQQAT: LIVE rejim yoqilgan! Real pul bilan savdo qilinadi.")
    else:
        log.info("Demo rejim — xavfsiz. Real pul ishlatilmaydi.")


def main() -> None:
    check_environment()
    log.info("Skelet tayyor. Keyingi qadam: MT5 ulanish moduli (app/market).")


if __name__ == "__main__":
    main()
