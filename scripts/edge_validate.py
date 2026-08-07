"""
TITAN AI — Faza 1 edge VALIDATSIYA (keng data, DEV PC MT5).

Jonli 199 signaldagi LEADLARni (sessiya-vaqti, M15>M5, EURUSD-yuk,
"trend" ovozi zarari) MINGLAB namunada tekshiradi. Har savdo uchun 7 ovoz
belgisi + kontekst (simvol/TF/soat/yo'nalish/confidence/strength) yoziladi
va CSV ga saqlanadi (keyingi ML uchun ham).

MUHIM: bu FAQAT O'LCHOV/tahlil — jonli botga tegmaydi. DEV PC MT5 ishlatiladi
(server ko'prigi emas), shuning uchun jonli signal oqimiga xavf yo'q.
Metrika: bitta TP (tp2, RR~1:2) vs SL, spread xarajati chegirilgan sof R.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime

import MetaTrader5 as mt5
import pandas as pd

from app.ai.fusion_engine import FusionEngine
from app.core.constants import Direction

SYMBOLS = ["EURUSD", "USDJPY", "USDCHF", "GBPUSD"]
TF_MAP = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
BARS = {"M5": 15000, "M15": 20000}   # ~52 kun M5 / ~200 kun M15
WINDOW = 160
SPREAD_FLOOR_POINTS = 15             # realistik minimal spread
OUT_CSV = "scratchpad/edge_dataset.csv"


def fetch(symbol: str, tf_key: str) -> tuple[pd.DataFrame, float, int]:
    rates = mt5.copy_rates_from_pos(symbol, TF_MAP[tf_key], 0, BARS[tf_key])
    if rates is None or len(rates) == 0:
        return pd.DataFrame(), 0.0, 5
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")[["open", "high", "low", "close"]]
    info = mt5.symbol_info(symbol)
    point = info.point if info else 1e-5
    digits = info.digits if info else 5
    spread_pts = max(info.spread if info else 0, SPREAD_FLOOR_POINTS)
    spread_price = spread_pts * point
    return df, spread_price, digits


def run_symbol_tf(engine, symbol, tf_key, rows):
    df, spread, digits = fetch(symbol, tf_key)
    if df.empty or len(df) < WINDOW + 50:
        print(f"  {symbol} {tf_key}: data yetarli emas")
        return
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    times = df.index
    n = len(df)
    i = WINDOW
    open_t = None
    count = 0
    while i < n:
        if open_t is not None:
            hi, lo = highs[i], lows[i]
            d, entry, sl, tp = open_t["dir"], open_t["entry"], open_t["sl"], open_t["tp"]
            sl_dist = abs(entry - sl) or 1e-9
            rr = abs(tp - entry) / sl_dist
            cost_r = spread / sl_dist
            hit = None
            if d == Direction.BUY:
                if lo <= sl: hit = ("loss", -1.0)
                elif hi >= tp: hit = ("win", rr)
            else:
                if hi >= sl: hit = ("loss", -1.0)
                elif lo <= tp: hit = ("win", rr)
            if hit:
                gross = hit[1]
                open_t["r"] = round(gross - cost_r, 4)
                open_t["won"] = 1 if hit[0] == "win" else 0
                rows.append(open_t)
                count += 1
                open_t = None
            i += 1
            continue

        window_df = df.iloc[max(0, i - WINDOW): i + 1]
        res = engine.analyze(window_df, symbol, tf_key, digits=digits,
                             now=times[i].to_pydatetime())
        if res.is_signal:
            s = res.signal
            active = {v.strategy: (1 if v.direction == s.direction else 0) for v in s.votes}
            open_t = {
                "symbol": symbol, "tf": tf_key, "dir": s.direction,
                "dir_s": s.direction.value, "hour": times[i].hour,
                "conf": round(float(s.confidence), 1), "strength": s.strength.value,
                "entry": s.entry, "sl": s.stop_loss, "tp": s.take_profit,
                **{f"v_{k}": v for k, v in active.items()},
            }
        i += 1
    print(f"  {symbol} {tf_key}: {count} savdo")


def _stats(rs):
    n = len(rs)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    wins = sum(1 for r in rs if r > 0)
    g = sum(rs)
    return n, 100 * wins / n, g / n, g


def _line(n, wr, exp, g):
    return f"n={n:5d}  win={wr:5.1f}%  exp={exp:+.3f}R  gross={g:+7.1f}R"


def report(rows):
    allR = [r["r"] for r in rows]
    print("\n" + "=" * 62)
    print("  FAZA 1 EDGE VALIDATSIYA (keng data)")
    print("=" * 62)
    print("UMUMIY:", _line(*_stats(allR)))

    def bd(title, keyfn, min_n=20, sort_n=True):
        print(f"\n--- {title} ---")
        g = defaultdict(list)
        for r in rows:
            g[keyfn(r)].append(r["r"])
        items = sorted(g.items(), key=(lambda kv: -len(kv[1])) if sort_n else (lambda kv: str(kv[0])))
        for k, rs in items:
            n, wr, e, gr = _stats(rs)
            if n < min_n:
                continue
            print(f"  {str(k):10} {_line(n, wr, e, gr)}")

    bd("SIMVOL", lambda r: r["symbol"])
    bd("TIMEFRAME", lambda r: r["tf"])
    bd("YO'NALISH", lambda r: r["dir_s"])
    bd("SOAT (UTC)", lambda r: f"{r['hour']:02d}", sort_n=False)
    def cb(cf):
        cf = float(cf)
        return "60-64" if cf < 65 else "65-69" if cf < 70 else "70-74" if cf < 75 else "75-79" if cf < 80 else "80+"
    bd("CONFIDENCE", lambda r: cb(r["conf"]), sort_n=False)

    print("\n--- OVOZ (BELGI): strategiya signal yo'nalishida FAOL bo'lsa ---")
    strat_keys = sorted({k[2:] for r in rows for k in r if k.startswith("v_")})
    for st in strat_keys:
        col = f"v_{st}"
        act = [r["r"] for r in rows if r.get(col) == 1]
        ina = [r["r"] for r in rows if r.get(col) == 0]
        na, _, ea, _ = _stats(act)
        ni, _, ei, _ = _stats(ina)
        if na >= 20 and ni >= 20:
            edge = ea - ei
            flag = "  <-- IJOBIY" if edge > 0.05 else ("  <-- ZARARLI" if edge < -0.05 else "")
            print(f"  {st:16} FAOL exp={ea:+.3f}(n={na})  NOFAOL exp={ei:+.3f}(n={ni})  farq={edge:+.3f}{flag}")
    print("=" * 62)
    print(f"  Jami savdo: {len(rows)}  |  CSV: {OUT_CSV}")
    print("=" * 62)


def main():
    if not mt5.initialize():
        print("MT5 initialize FAILED:", mt5.last_error())
        return
    print("MT5 ulandi:", mt5.account_info().login, "| boshlanish:", datetime.now().strftime("%H:%M:%S"))
    engine = FusionEngine()
    rows = []
    for sym in SYMBOLS:
        for tf in TF_MAP:
            run_symbol_tf(engine, sym, tf, rows)
    mt5.shutdown()

    if rows:
        keys = sorted({k for r in rows for k in r})
        import os
        os.makedirs("scratchpad", exist_ok=True)
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: (r[k].value if hasattr(r.get(k), "value") else r.get(k)) for k in keys})
        report(rows)
    print("TUGADI:", datetime.now().strftime("%H:%M:%S"))


if __name__ == "__main__":
    main()
