"""
Grafik chizishni sinash — signal topib, uni PNG grafik qilib chizadi.

Ishga tushirish (MT5 terminal ochiq):
  venv\\Scripts\\python.exe scripts\\test_chart.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import FusionEngine  # noqa: E402
from app.charting import ChartRenderer, Zone  # noqa: E402
from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402
from app.smc import FVGAnalyzer, OrderBlockAnalyzer  # noqa: E402

SYMBOLS = ["USDCHF", "USDJPY", "EURUSD", "XAUUSD", "GBPUSD", "AUDUSD"]
TIMEFRAMES = [Timeframe.M5, Timeframe.M15, Timeframe.H1, Timeframe.H4]


def build_zones(df, price, avg_range) -> list[Zone]:
    """Narxga yaqin fresh OB va FVG zonalarini grafik uchun tayyorlaydi."""
    zones: list[Zone] = []
    near = 3 * avg_range
    for b in OrderBlockAnalyzer().find(df):
        if not b.mitigated and (b.bottom - near) <= price <= (b.top + near):
            zones.append(Zone(b.bottom, b.top, "#f7b731", f"OB {b.direction.value}"))
    for g in FVGAnalyzer().find(df):
        if not g.filled and (g.bottom - near) <= price <= (g.top + near):
            zones.append(Zone(g.bottom, g.top, "#a55eea", f"FVG {g.direction.value}"))
    return zones[:4]


def main() -> None:
    conn = MT5Connector()
    engine = FusionEngine()
    renderer = ChartRenderer()
    try:
        conn.connect()
        feed = DataFeed()
        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                info = feed.get_symbol_info(symbol)
                df = feed.get_candles(symbol, tf, count=200)
                res = engine.analyze(df, symbol, tf.value, digits=info.digits)
                if not res.is_signal:
                    continue

                sig = res.signal
                log.info(f"🎯 {sig.summary()}")
                avg_range = float((df["high"] - df["low"]).mean())
                zones = build_zones(df, sig.price_at_signal, avg_range)
                path = renderer.render(df, sig, zones=zones)
                log.info(f"✅ Grafik tayyor: {path}")
                return

        log.info("Signal topilmadi (WAIT). Grafik chizilmadi.")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
