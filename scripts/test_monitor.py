"""
Position Monitor mantiqini sinash (deterministik — jonli narxga bog'liq emas).

BUY pozitsiya TP tomon 60% yurgan holatда SL to'g'ri ko'chirilishini tekshiradi.
MT5 chaqiruvlari (tick, symbol_info, modify) stub qilinadi.

Ishga tushirish:
  venv\\Scripts\\python.exe scripts\\test_monitor.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.core.constants import Direction, TITAN_MAGIC  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.execution import PositionMonitor, TradeExecutor  # noqa: E402
from app.execution.executor import Position, TradeResult  # noqa: E402
from app.market.data_feed import SymbolInfo, Tick  # noqa: E402


def make_symbol_info() -> SymbolInfo:
    return SymbolInfo(
        name="EURUSD", digits=5, point=0.00001, spread=1, trade_allowed=True,
        volume_min=0.01, volume_max=100, volume_step=0.01,
        tick_size=0.00001, tick_value=1.0, stops_level=0, filling_mode=2,
    )


def main() -> None:
    executor = TradeExecutor()
    monitor = PositionMonitor(executor)

    captured = {}

    # --- MT5 chaqiruvlarini stub qilamiz ---
    monitor.feed.get_symbol_info = lambda symbol: make_symbol_info()
    monitor.feed.get_tick = lambda symbol: Tick(
        symbol="EURUSD", bid=1.10300, ask=1.10302, spread=0.00002,
        time=pd.Timestamp.now(),
    )

    def fake_modify(ticket, sl=None, tp=None):
        captured["sl"] = sl
        return TradeResult(success=True, retcode=0, message="ok", order=ticket)

    executor.modify_sltp = fake_modify

    # BUY: entry 1.10000, TP 1.10500, SL 1.09500 -> hozir narx 1.10300 (60% TP tomon)
    pos = Position(
        ticket=999, symbol="EURUSD", direction=Direction.BUY,
        volume=0.01, price_open=1.10000, sl=1.09500, tp=1.10500,
        profit=3.0, magic=TITAN_MAGIC,
    )

    log.info("Test: BUY entry=1.10000 TP=1.10500 SL=1.09500 narx=1.10300 (60%)")
    result = monitor._manage_one(pos)
    log.info(f"Natija: {result}")
    log.info(f"Yangi SL: {captured.get('sl')}")

    # Kutilgan: trailing => SL = entry + (price-entry)*0.5 = 1.10000 + 0.00300*0.5 = 1.10150
    expected = 1.10150
    got = captured.get("sl")
    if got == expected:
        log.info(f"✅ TO'G'RI! SL {got} (kutilgan {expected}) — trailing ishladi, foyda qulflandi")
    else:
        log.error(f"❌ Kutilgan {expected}, olindi {got}")

    # 2-test: hali foydada emas (narx entry pastida) -> hech narsa qilmasin
    monitor.feed.get_tick = lambda symbol: Tick(
        symbol="EURUSD", bid=1.09900, ask=1.09902, spread=0.00002, time=pd.Timestamp.now(),
    )
    captured.clear()
    pos2 = Position(ticket=1000, symbol="EURUSD", direction=Direction.BUY,
                    volume=0.01, price_open=1.10000, sl=1.09500, tp=1.10500,
                    profit=-1.0, magic=TITAN_MAGIC)
    r2 = monitor._manage_one(pos2)
    log.info(f"2-test (zararда): natija={r2}, SL o'zgardimi={captured.get('sl')}")
    if r2 is None and not captured:
        log.info("✅ TO'G'RI! Zararдаги savdo tegilmadi.")


if __name__ == "__main__":
    main()
