"""
Execution Engine'ni DEMO account'da sinash — haqiqiy savdo ochadi va yopadi.

Xavfsizlik: kichik 0.01 lot bilan ochiladi, 3 soniyadan keyin yopiladi.
Faqat DEMO account'da ishlaydi.

Ishga tushirish (MT5 terminal ochiq, demo'ga kirilgan):
  venv\\Scripts\\python.exe scripts\\test_execution.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai import FusionEngine  # noqa: E402
from app.ai.signal import Signal  # noqa: E402
from app.core.constants import Direction, SignalStrength, Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.execution import TradeExecutor  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402

SYMBOLS = ["USDCHF", "USDJPY", "EURUSD", "XAUUSD", "GBPUSD"]
TIMEFRAMES = [Timeframe.M5, Timeframe.M15, Timeframe.H1]


def find_signal(engine, feed) -> Signal | None:
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            info = feed.get_symbol_info(symbol)
            df = feed.get_candles(symbol, tf, count=200)
            res = engine.analyze(df, symbol, tf.value, digits=info.digits)
            if res.is_signal:
                return res.signal
    return None


def manual_signal(feed) -> Signal:
    """Signal topilmasa — EURUSD uchun qo'lda test signali."""
    info = feed.get_symbol_info("EURUSD")
    tick = feed.get_tick("EURUSD")
    entry = tick.ask
    sl = round(entry - 0.0030, info.digits)
    tp = round(entry + 0.0060, info.digits)
    return Signal(
        symbol="EURUSD", timeframe="M15", direction=Direction.BUY,
        confidence=70, strength=SignalStrength.MEDIUM,
        entry=entry, stop_loss=sl, take_profit=tp, risk_reward=2.0,
        price_at_signal=entry, buy_score=70, sell_score=0,
    )


def main() -> None:
    conn = MT5Connector()
    feed = DataFeed()
    executor = TradeExecutor(conn, feed)
    engine = FusionEngine()

    try:
        conn.connect()
        acc = conn.account_info()
        if not acc.is_demo:
            log.error("❌ Bu REAL account! Test to'xtatildi (faqat demo).")
            return

        log.info(f"Balans (avval): {acc.balance} {acc.currency}")

        signal = find_signal(engine, feed) or manual_signal(feed)
        log.info(f"Test signali: {signal.summary()}")

        # Risk asosida lot QANDAY hisoblanishini ko'rsatamiz (ochmaymiz — faqat ma'lumot)
        from app.risk import PositionSizer
        info = feed.get_symbol_info(signal.symbol)
        calc = PositionSizer().calculate(acc.balance, 1.0, signal.entry, signal.stop_loss, info)
        log.info(f"ℹ️  Risk 1% bo'lsa lot = {calc.lot} "
                 f"(risk {calc.risk_amount} {acc.currency}, loss/lot={calc.loss_per_lot})")

        # --- Xavfsiz test: 0.01 lot bilan ochamiz ---
        log.info("Test uchun 0.01 lot bilan savdo ochilmoqda...")
        result = executor.open_signal(signal, lot=0.01)
        if not result.success:
            log.error(f"❌ Savdo ochilmadi: retcode={result.retcode} — {result.message}")
            return

        log.info(f"✅ OCHILDI: ticket={result.order} price={result.price} lot={result.volume}")

        # --- Ochiq pozitsiyalarni ko'rsatamiz ---
        for p in executor.positions(signal.symbol):
            log.info(f"   Pozitsiya: #{p.ticket} {p.symbol} {p.direction.value} "
                     f"lot={p.volume} open={p.price_open} SL={p.sl} TP={p.tp} "
                     f"profit={p.profit} magic={p.magic}")

        log.info("3 soniya kutilmoqda (siz MT5 terminalda savdoni ko'rishingiz mumkin)...")
        time.sleep(3)

        # --- Yopamiz ---
        log.info("Savdo yopilmoqda...")
        close = executor.close_position(result.order)
        if close.success:
            log.info(f"✅ YOPILDI: ticket={close.order} price={close.price}")
        else:
            log.error(f"❌ Yopilmadi: {close.message}")

        acc2 = conn.account_info()
        log.info(f"Balans (keyin): {acc2.balance} {acc2.currency}")
        log.info("✅ Execution to'liq tsikl (ochish + yopish) muvaffaqiyatli!")

    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
