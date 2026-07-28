"""
Fusion Engine'ni real MT5 ma'lumotida sinash — signal + to'liq ball taqsimoti.

Ishga tushirish (MT5 terminal ochiq bo'lsin):
  venv\\Scripts\\python.exe scripts\\test_fusion.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import FusionEngine  # noqa: E402
from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402

SYMBOLS = ["EURUSD", "XAUUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
TIMEFRAMES = [Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4]


def print_votes(result) -> None:
    for v in result.votes:
        mark = {"BUY": "🟢", "SELL": "🔴", "WAIT": "⚪"}[v.direction.value]
        log.info(f"    {mark} {v.strategy:<12} vazn={v.weight:<4.0f} "
                 f"conf={v.confidence:<3.0f} — {v.reason}")
    log.info(f"    ➤ BUY={result.buy_score}  SELL={result.sell_score}  "
             f"=> {result.direction.value}  confidence={result.confidence}%")


def main() -> None:
    conn = MT5Connector()
    engine = FusionEngine()
    signals = []
    try:
        conn.connect()
        feed = DataFeed()

        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    info = feed.get_symbol_info(symbol)
                    df = feed.get_candles(symbol, tf, count=200)
                    res = engine.analyze(df, symbol, tf.value, digits=info.digits)

                    if res.is_signal:
                        signals.append(res.signal)
                        log.info("=" * 62)
                        log.info(f"  🎯 SIGNAL TOPILDI: {res.signal.summary()}")
                        print_votes(res)
                        log.info("=" * 62)
                    else:
                        log.info(f"⚪ {symbol} {tf.value}: WAIT "
                                 f"(BUY={res.buy_score} SELL={res.sell_score} "
                                 f"conf={res.confidence}% — {res.wait_reason})")
                except Exception as e:  # noqa: BLE001
                    log.error(f"{symbol} {tf.value}: {e}")

        log.info("=" * 62)
        log.info(f"✅ Skaner yakunlandi. Signallar: {len(signals)} ta "
                 f"({len(SYMBOLS)}x{len(TIMEFRAMES)} = {len(SYMBOLS)*len(TIMEFRAMES)} tekshiruv)")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
