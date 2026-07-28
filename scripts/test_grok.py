"""
Grok mijozini sinash — signal topib, uni tushuntiradi.

Key .env da bo'lmasa: zaxira (fallback) izoh ishlatiladi.
Key qo'shilsa: haqiqiy Grok tahlili chiqadi. Kod bir xil ishlaydi.

Ishga tushirish (MT5 terminal ochiq):
  venv\\Scripts\\python.exe scripts\\test_grok.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import FusionEngine, GrokClient  # noqa: E402
from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402

SYMBOLS = ["USDCHF", "USDJPY", "EURUSD", "XAUUSD", "GBPUSD", "AUDUSD"]
TIMEFRAMES = [Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4]


def main() -> None:
    conn = MT5Connector()
    engine = FusionEngine()
    grok = GrokClient()

    log.info(f"Grok API sozlangan: {grok.is_configured}")

    try:
        conn.connect()
        feed = DataFeed()

        # Birinchi topilgan signalni tushuntiramiz
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                info = feed.get_symbol_info(symbol)
                df = feed.get_candles(symbol, tf, count=200)
                res = engine.analyze(df, symbol, tf.value, digits=info.digits)
                if not res.is_signal:
                    continue

                sig = res.signal
                log.info("=" * 62)
                log.info(f"  🎯 {sig.summary()}")
                log.info("=" * 62)

                # --- Grok tushuntirish ---
                log.info("  📝 Grok'ga yuboriladigan so'rov (prompt):")
                for line in grok.build_prompt(sig).splitlines():
                    log.info(f"     {line}")

                explanation = grok.explain_signal(sig)
                sig.ai_explanation = explanation
                log.info("-" * 62)
                log.info("  🤖 TUSHUNTIRISH:")
                for line in explanation.splitlines():
                    log.info(f"     {line}")
                log.info("=" * 62)
                return  # bitta signal yetarli

        log.info("Hozircha signal topilmadi (bozor WAIT holatida).")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
