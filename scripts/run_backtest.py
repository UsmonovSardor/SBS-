"""
TITAN AI — Edge isbotlash backtesti (Faza B).

Har simvol×taymfrejm uchun XARAJATLI (spread) backtest o'tkazadi va:
  - to'liq davr, train(70%) va test(30%) natijalarini,
  - A/B taqqoslashni (Faza A [8 ovoz]  vs  faqat 6-ovoz [htf_bias+premium_discount o'chirilgan])
ko'rsatadi. Maqsad: Faza A qo'shimchalari va umuman strategiya SPREAD'dan keyin
ham ijobiy edge (expectancy > 0) beryaptimi — buni raqamда ko'rish.

Ishga tushirish (MT5 terminal ochiq/ulangan bo'lsin):
  venv\\Scripts\\python.exe scripts\\run_backtest.py

Eslatma: bu ko'p hisob-kitob (bir necha daqiqa). Jonli bot bilan bir MT5'ni
bo'lishmaslik uchun backtestni alohida (dev) mashinada yoki botni vaqtincha
to'xtatib ishga tushirish tavsiya etiladi.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Konsol cp1251 bo'lsa ham unicode (×, →, ✅) yozilaverishi uchun
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from app.ai import FusionEngine  # noqa: E402
from app.backtesting import Backtester, BacktestResult  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402

# --- Sozlamalar ---
SYMBOLS = settings.symbols
TIMEFRAMES = [Timeframe.M15]          # kerak bo'lsa: Timeframe.M5, Timeframe.H1 qo'shing
HISTORY = 3000                        # nechta tarixiy sham
TRAIN_FRAC = 0.70
# MT5 ayni lahzalik spred ba'zan 0 ko'rsatadi (tinch bozor). Halol xarajat uchun
# realistik minimal spred (punkt) qo'yamiz — max(lahzalik, floor).
MIN_SPREAD_POINTS = 15
DISABLED_FOR_AB = {"htf_bias", "premium_discount"}  # A/B: Faza A qo'shimchalarini o'chirish

COLS = ["trades", "win_rate", "expectancy", "total_r", "gross_r",
        "cost_r", "profit_factor", "sharpe", "max_dd_r", "max_consec_loss"]
HDR = f"{'label':<18}{'trades':>7}{'WR%':>7}{'expect':>8}{'netR':>8}" \
      f"{'grossR':>8}{'costR':>8}{'PF':>6}{'Shrp':>6}{'maxDD':>7}{'cLoss':>6}"


def _row(label: str, r: BacktestResult) -> str:
    s = r.summary()
    pf = "inf" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"
    return (f"{label:<18}{s['trades']:>7}{s['win_rate']:>7}{s['expectancy']:>8}"
            f"{s['total_r']:>8}{s['gross_r']:>8}{s['cost_r']:>8}{pf:>6}"
            f"{s['sharpe']:>6}{s['max_dd_r']:>7}{s['max_consec_loss']:>6}")


def _bt(df, engine, symbol, tf, spread, digits) -> BacktestResult:
    return Backtester(engine=engine, spread=spread).run(df, symbol, tf, digits=digits)


def main() -> None:
    conn = MT5Connector()
    agg = {"A_net": 0.0, "B_net": 0.0, "A_trades": 0, "B_trades": 0}
    try:
        conn.connect()
        feed = DataFeed()
        engine_a = FusionEngine()                              # Faza A (8 ovoz)
        engine_b = FusionEngine(disabled=DISABLED_FOR_AB)      # faqat 6 ovoz

        for symbol in SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    info = feed.get_symbol_info(symbol)
                    spread = max(info.spread, MIN_SPREAD_POINTS) * info.point
                    df = feed.get_candles(symbol, tf, count=HISTORY)
                    split = int(len(df) * TRAIN_FRAC)
                    log.info(f"⏳ {symbol} {tf.value}: {len(df)} sham, spread={spread:.5f} — hisoblanmoqda...")

                    full_a = _bt(df, engine_a, symbol, tf.value, spread, info.digits)
                    train_a = _bt(df.iloc[:split], engine_a, symbol, tf.value, spread, info.digits)
                    test_a = _bt(df.iloc[split:], engine_a, symbol, tf.value, spread, info.digits)
                    full_b = _bt(df, engine_b, symbol, tf.value, spread, info.digits)

                    print("\n" + "=" * 92)
                    print(f"  {symbol} {tf.value}   (spread={spread:.5f}, {len(df)} sham)")
                    print("=" * 92)
                    print(HDR)
                    print("-" * 92)
                    print(_row("FAZA A (8 ovoz)", full_a))
                    print(_row("  train 70%", train_a))
                    print(_row("  test 30%", test_a))
                    print(_row("6-OVOZ (A/B)", full_b))

                    agg["A_net"] += full_a.total_r
                    agg["B_net"] += full_b.total_r
                    agg["A_trades"] += full_a.total
                    agg["B_trades"] += full_b.total
                except Exception as e:  # noqa: BLE001
                    log.error(f"{symbol} {tf.value}: {e}")

        print("\n" + "#" * 92)
        print("  UMUMIY XULOSA (barcha simvol×TF, sof R = spread'dan keyin)")
        print("#" * 92)
        print(f"  FAZA A (8 ovoz):  net R = {agg['A_net']:.2f}   ({agg['A_trades']} savdo)")
        print(f"  6-OVOZ (A/B)   :  net R = {agg['B_net']:.2f}   ({agg['B_trades']} savdo)")
        delta = agg["A_net"] - agg["B_net"]
        verdict = ("Faza A qo'shimchalari FOYDA berdi ✅" if delta > 0
                   else "Faza A qo'shimchalari foyda bermadi ❌" if delta < 0
                   else "farq yo'q")
        print(f"  FARQ (A - B)   :  {delta:+.2f} R  →  {verdict}")
        print("#" * 92)
        print("\n  Izoh: expectancy > 0 va PF > 1 bo'lsa — ijobiy edge (spread'dan keyin).")
        print("  test(30%) natijasi train(70%) ga o'xshash bo'lsa — barqaror (overfit emas).")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
