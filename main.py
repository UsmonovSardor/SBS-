"""
TITAN AI — Kirish nuqtasi (entry point).

Real-time rejimда ishga tushiradi: bozorni uzluksiz skanlaydi, signal topsa
Telegram guruhga (grafik + tahlil + Auto-Trade tugma) yuboradi.

Ishga tushirish:
    python main.py
To'xtatish: Ctrl+C
"""
from __future__ import annotations

import asyncio

from app import __version__
from app.core.config import settings
from app.core.logger import log


def check_environment() -> bool:
    """Sozlamalar to'ldirilganini tekshiradi. Ishga tushirish mumkinmi?"""
    log.info("=" * 55)
    log.info(f"  TITAN AI  v{__version__}  tekshiruv...")
    log.info("=" * 55)

    checks = {
        "MT5 (terminal orqali)": True,  # ochiq terminal sessiyasiga ulanadi
        "AI API key (Groq)": bool(settings.grok_api_key),
        "Telegram token": bool(settings.telegram_bot_token),
        "Telegram kanal": bool(settings.telegram_channel_id),
    }
    for name, ok in checks.items():
        status = "✅" if ok else "⚠️  yo'q"
        log.info(f"  {name:<24} {status}")

    if not settings.telegram_bot_token or not settings.telegram_channel_id:
        log.error("Telegram sozlanmagan (.env) — bot ishga tushmaydi.")
        return False
    if not settings.grok_api_key:
        log.warning("AI key yo'q — signal izohlari zaxira rejimda bo'ladi.")
    if settings.is_live:
        log.warning("⚠️  LIVE rejim! Real pul bilan savdo. Ehtiyot bo'ling.")
    return True


async def _run() -> None:
    from app.orchestrator import TitanOrchestrator

    orch = TitanOrchestrator()
    try:
        await orch.run()
    finally:
        await orch.close()


def main() -> None:
    if not check_environment():
        return
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        log.info("TITAN AI to'xtatildi (Ctrl+C).")


if __name__ == "__main__":
    main()
