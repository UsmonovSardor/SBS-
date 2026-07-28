"""
Backtest — strategiyani tarixiy ma'lumotда sinash.

Ishga tushirish (MT5 terminal ochiq):
  venv\\Scripts\\python.exe scripts\\backtest_run.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.backtesting import Backtester  # noqa: E402
from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402

TESTS = [
    ("EURUSD", Timeframe.M15),
    ("XAUUSD", Timeframe.M15),
    ("EURUSD", Timeframe.H1),
]
BARS = 2000


def main() -> None:
    conn = MT5Connector()
    conn.connect()
    feed = DataFeed()
    bt = Backtester()

    log.info(f"Backtest: har biri {BARS} sham")
    log.info("=" * 60)

    grand_r = 0.0
    grand_trades = 0
    for symbol, tf in TESTS:
        info = feed.get_symbol_info(symbol)
        df = feed.get_candles(symbol, tf, count=BARS)
        res = bt.run(df, symbol, tf.value, digits=info.digits)

        log.info(f"📊 {symbol} {tf.value}  ({len(df)} sham, "
                 f"{df.index[0].date()} — {df.index[-1].date()})")
        log.info(f"   Savdolar: {res.total}  |  ✅ {res.wins}  ❌ {res.losses}  "
                 f"|  Win-rate: {res.win_rate}%")
        log.info(f"   Umumiy R: {res.total_r}  |  Profit Factor: {res.profit_factor}  "
                 f"|  Max Drawdown: {res.max_drawdown_r} R")
        log.info("-" * 60)
        grand_r += res.total_r
        grand_trades += res.total

    log.info(f"🎯 JAMI: {grand_trades} savdo, {round(grand_r, 2)} R")
    log.info("   (R = risk birligi. Har yutuq +RR, yutqaziq -1. Musbat R = foydali.)")
    conn.disconnect()


if __name__ == "__main__":
    main()
