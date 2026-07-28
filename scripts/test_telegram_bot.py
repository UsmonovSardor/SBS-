"""
Telegram bot + Auto-Trade tugmasini TO'LIQ sinash (interaktiv).

1) Signal topadi, grafik+tahlil bilan guruhga yuboradi
2) Polling boshlaydi — Auto-Trade tugmasi JONLI bo'ladi
3) Siz guruhда "🟢 Auto-Trade" ni bosasiz -> MT5 demo'da savdo ochiladi

To'xtatish: Ctrl+C (yoki jarayonni to'xtatish).

Ishga tushirish (MT5 terminal ochiq, AutoTrading yoqilgan):
  venv\\Scripts\\python.exe scripts\\test_telegram_bot.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import FusionEngine, GrokClient  # noqa: E402
from app.ai.signal import Signal  # noqa: E402
from app.charting import ChartRenderer, Zone  # noqa: E402
from app.core.constants import Direction, SignalStrength, Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.execution import TradeExecutor  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402
from app.smc import FVGAnalyzer, OrderBlockAnalyzer  # noqa: E402
from app.telegram import TitanTelegramBot  # noqa: E402

SYMBOLS = ["USDCHF", "USDJPY", "EURUSD", "XAUUSD", "GBPUSD"]
TIMEFRAMES = [Timeframe.M5, Timeframe.M15, Timeframe.H1]


def build_zones(df, price, avg_range):
    zones = []
    near = 3 * avg_range
    for b in OrderBlockAnalyzer().find(df):
        if not b.mitigated and (b.bottom - near) <= price <= (b.top + near):
            zones.append(Zone(b.bottom, b.top, "#f7b731", f"OB {b.direction.value}"))
    for g in FVGAnalyzer().find(df):
        if not g.filled and (g.bottom - near) <= price <= (g.top + near):
            zones.append(Zone(g.bottom, g.top, "#a55eea", f"FVG {g.direction.value}"))
    return zones[:4]


def manual_signal(feed) -> Signal:
    info = feed.get_symbol_info("EURUSD")
    tick = feed.get_tick("EURUSD")
    entry = tick.ask
    return Signal(
        symbol="EURUSD", timeframe="M15", direction=Direction.BUY,
        confidence=72, strength=SignalStrength.MEDIUM,
        entry=entry, stop_loss=round(entry - 0.0030, info.digits),
        take_profit=round(entry + 0.0060, info.digits), risk_reward=2.0,
        price_at_signal=entry, buy_score=72, sell_score=0,
    )


async def main() -> None:
    conn = MT5Connector()
    conn.connect()
    feed = DataFeed()
    executor = TradeExecutor(conn, feed)
    engine = FusionEngine()
    grok = GrokClient()
    renderer = ChartRenderer()

    signal, sig_df = None, None
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            info = feed.get_symbol_info(symbol)
            df = feed.get_candles(symbol, tf, count=200)
            res = engine.analyze(df, symbol, tf.value, digits=info.digits)
            if res.is_signal:
                signal, sig_df = res.signal, df
                break
        if signal:
            break
    if signal is None:
        signal = manual_signal(feed)
        sig_df = feed.get_candles(signal.symbol, Timeframe.M15, count=200)

    signal.ai_explanation = grok.explain_signal(signal)
    avg_range = float((sig_df["high"] - sig_df["low"]).mean())
    zones = build_zones(sig_df, signal.price_at_signal, avg_range)
    chart = renderer.render(sig_df, signal, zones=zones)

    bot = TitanTelegramBot(executor=executor)
    await bot.send_signal(signal, chart)
    log.info("=" * 55)
    log.info("  ✅ Signal yuborildi. Endi guruhда '🟢 Auto-Trade' ni bosing!")
    log.info("  Bot polling'da — tugma JONLI. To'xtatish: Ctrl+C")
    log.info("=" * 55)
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot to'xtatildi.")
