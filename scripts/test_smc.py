"""
SMC tahlil modullarini real MT5 ma'lumotida sinash.

Ishga tushirish (loyiha ildizidan, MT5 terminal ochiq bo'lsin):
  venv\\Scripts\\python.exe scripts\\test_smc.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402
from app.smc import (  # noqa: E402
    FVGAnalyzer,
    LiquidityAnalyzer,
    OrderBlockAnalyzer,
    StructureAnalyzer,
)


def analyze_symbol(feed: DataFeed, symbol: str, tf: Timeframe = Timeframe.M15) -> None:
    df = feed.get_candles(symbol, tf, count=200)
    log.info("=" * 60)
    log.info(f"  {symbol}  ({tf.value})  —  {len(df)} ta sham")
    log.info(f"  Oxirgi narx: {df['close'].iloc[-1]}")
    log.info("=" * 60)

    # 1) Market Structure
    structure = StructureAnalyzer(lookback=2).analyze(df)
    log.info(f"📐 TREND: {structure.trend.value}")
    log.info(f"   Swing High: {len(structure.swing_highs)} ta, "
             f"Swing Low: {len(structure.swing_lows)} ta")
    log.info(f"   Struktura hodisalari (BOS/CHoCH): {len(structure.events)} ta")
    if structure.last_event:
        e = structure.last_event
        log.info(f"   Oxirgi: {e.kind} [{e.direction.value}] "
                 f"narx={e.price:.5f} vaqt={e.time}")

    # 2) Order Blocks
    obs = OrderBlockAnalyzer().find(df)
    fresh_obs = [b for b in obs if not b.mitigated]
    log.info(f"🟦 ORDER BLOCK: {len(obs)} ta (fresh: {len(fresh_obs)})")
    for b in fresh_obs[-3:]:
        log.info(f"   {b.direction.value}  [{b.bottom:.5f} — {b.top:.5f}]  "
                 f"kuch={b.strength}x  vaqt={b.time}")

    # 3) Fair Value Gaps
    fvgs = FVGAnalyzer().find(df)
    fresh_fvgs = [g for g in fvgs if not g.filled]
    log.info(f"🟪 FVG: {len(fvgs)} ta (fresh: {len(fresh_fvgs)})")
    for g in fresh_fvgs[-3:]:
        log.info(f"   {g.direction.value}  [{g.bottom:.5f} — {g.top:.5f}]  vaqt={g.time}")

    # 4) Liquidity
    pools, sweeps = LiquidityAnalyzer().analyze(df)
    log.info(f"💧 LIQUIDITY: {len(pools)} ta pool, {len(sweeps)} ta sweep")
    for p in pools[-3:]:
        state = "yig'ilgan" if p.swept else "faol"
        log.info(f"   {p.kind}  daraja={p.price:.5f}  ({len(p.points)} nuqta, {state})")
    for s in sweeps[-2:]:
        log.info(f"   SWEEP -> {s.direction.value}  daraja={s.level:.5f}  vaqt={s.time}")


def main() -> None:
    conn = MT5Connector()
    try:
        conn.connect()
        feed = DataFeed()
        for symbol in ["EURUSD", "XAUUSD"]:
            try:
                analyze_symbol(feed, symbol)
            except Exception as e:  # noqa: BLE001
                log.error(f"{symbol} tahlil xatoligi: {e}")
        log.info("=" * 60)
        log.info("✅ SMC tahlil test yakunlandi.")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
