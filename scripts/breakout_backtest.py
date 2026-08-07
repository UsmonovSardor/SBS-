"""
TITAN/ScalperBot — Session Range Breakout v5 ni Python'da AYNAN takrorlab,
KENG (ko'p yil) out-of-sample backtest qiladi + ML filtri uchun belgilangan
dataset yozadi.

Mantiq (ScalperBot_Breakout_v5.mq5 dan):
  - Server-vaqti 00:00-08:00 M15 diapazon (Hi/Lo).
  - 08:00-20:00 breakout: c1 > Hi + 0.20*ATR -> BUY (SL=Lo-buffer);
                          c1 < Lo - 0.20*ATR -> SELL (SL=Hi+buffer).
  - TP = risk * 1.5. MinRange 1.0*ATR, MaxRange 10*ATR. Kuniga 1 buy + 1 sell,
    bir vaqtda 1 pozitsiya. Win=+1.5R, Loss=-1R. Spread/slippage xarajati chegiriladi.

FAQAT O'LCHOV/tahlil — jonli botga tegmaydi. DEV PC MT5.
"""
from __future__ import annotations

import csv
from collections import defaultdict

import numpy as np
import pandas as pd
import MetaTrader5 as mt5

SYMBOL = "XAUUSD"
TF = mt5.TIMEFRAME_M15
BARS = 50000             # terminalда mavjud maksimum (~2 yil M15: 2024-06->2026-08)
RANGE_START, RANGE_END = 0, 8
TRADE_START, TRADE_END = 8, 20
BUFFER_ATR = 0.20
RR = 1.5
MIN_RANGE_ATR = 1.0
MAX_RANGE_ATR = 10.0
ATR_PERIOD = 14
# Realistik xarajat (gold): spread ~25pt + slippage ~15pt = 0.40$ round-trip taxminan
SLIPPAGE_SPREAD_PRICE = 0.40
OUT_CSV = "scratchpad/breakout_dataset.csv"


def atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def load(symbol, tf, bars):
    r = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if r is None or len(r) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")  # server time (UTC+3)
    df = df.set_index("time")[["open", "high", "low", "close"]]
    df["atr"] = atr(df, ATR_PERIOD)
    df["date"] = df.index.date
    df["hour"] = df.index.hour
    df["dow"] = df.index.dayofweek
    return df


def backtest(df):
    trades = []
    days = sorted(set(df["date"]))
    prev_close = None
    for day in days:
        d = df[df["date"] == day]
        rng = d[(d["hour"] >= RANGE_START) & (d["hour"] < RANGE_END)]
        act = d[(d["hour"] >= TRADE_START) & (d["hour"] < TRADE_END)]
        if len(rng) < 3 or len(act) < 2:
            prev_close = d["close"].iloc[-1] if len(d) else prev_close
            continue
        hi, lo = rng["high"].max(), rng["low"].min()
        rsize = hi - lo
        bought = sold = False
        open_trade = None
        arr = act.reset_index()
        for i in range(1, len(arr)):
            row = arr.iloc[i]
            c1 = arr.iloc[i - 1]["close"]      # closed bar close
            a = arr.iloc[i - 1]["atr"]
            if not a or np.isnan(a) or a <= 0:
                continue
            # pozitsiya ochiq bo'lsa — chiqish tekshiruvi
            if open_trade is not None:
                hiP, loP = row["high"], row["low"]
                d_, e, sl, tp = open_trade[0], open_trade[1], open_trade[2], open_trade[3]
                if d_ == "BUY":
                    if loP <= sl: _close(open_trade, -1.0, trades); open_trade = None
                    elif hiP >= tp: _close(open_trade, RR, trades); open_trade = None
                else:
                    if hiP >= sl: _close(open_trade, -1.0, trades); open_trade = None
                    elif loP <= tp: _close(open_trade, RR, trades); open_trade = None
                continue
            # filtrlar
            if rsize < MIN_RANGE_ATR * a:
                continue
            if MAX_RANGE_ATR > 0 and rsize > MAX_RANGE_ATR * a:
                continue
            buf = BUFFER_ATR * a
            entry = row["open"]  # keyingi bar ochilishida kirish (realistik)
            feat_base = {
                "date": str(day), "hour": int(row["time"].hour), "dow": int(row["time"].dayofweek),
                "atr": round(float(a), 3), "range_atr": round(float(rsize / a), 3),
                "range_pts": round(float(rsize), 2),
                "prev_day_ret": round(float((rng["close"].iloc[-1] / prev_close - 1) * 100), 3) if prev_close else 0.0,
                "break_dist_atr": 0.0,
            }
            if (not bought) and c1 > hi + buf:
                sl = lo - buf
                sl_dist = entry - sl
                if sl_dist <= 0:
                    continue
                tp = entry + sl_dist * RR
                cost_r = SLIPPAGE_SPREAD_PRICE / sl_dist
                open_trade = ("BUY", entry, sl, tp, cost_r,
                              {**feat_base, "dir": "BUY",
                               "break_dist_atr": round(float((c1 - hi) / a), 3),
                               "sl_dist": round(float(sl_dist), 2)})
                bought = True
            elif (not sold) and c1 < lo - buf:
                sl = hi + buf
                sl_dist = sl - entry
                if sl_dist <= 0:
                    continue
                tp = entry - sl_dist * RR
                cost_r = SLIPPAGE_SPREAD_PRICE / sl_dist
                open_trade = ("SELL", entry, sl, tp, cost_r,
                              {**feat_base, "dir": "SELL",
                               "break_dist_atr": round(float((lo - c1) / a), 3),
                               "sl_dist": round(float(sl_dist), 2)})
                sold = True
        # kun oxirida ochiq pozitsiyani oxirgi narxда yopish (sessiya tugadi)
        if open_trade is not None:
            d_, e, sl, tp, cost_r, feat = open_trade
            last = arr.iloc[-1]["close"]
            gross = ((last - e) if d_ == "BUY" else (e - last)) / abs(e - sl)
            _close(open_trade, max(min(gross, RR), -1.0), trades)
        prev_close = d["close"].iloc[-1]
    return trades


def _close(open_trade, gross_r, trades):
    d_, e, sl, tp, cost_r, feat = open_trade
    net = round(gross_r - cost_r, 4)
    feat["r"] = net
    feat["won"] = 1 if net > 0 else 0
    trades.append(feat)


def metrics(rs):
    n = len(rs)
    if n == 0:
        return dict(n=0)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gw = sum(wins); gl = abs(sum(losses))
    eq = np.cumsum(rs); peak = np.maximum.accumulate(eq); dd = (eq - peak).min()
    return dict(
        n=n, win=round(100 * len(wins) / n, 1),
        exp=round(sum(rs) / n, 3), total_r=round(sum(rs), 1),
        pf=round(gw / gl, 2) if gl else float("inf"),
        maxdd_r=round(float(dd), 1),
        sharpe=round(np.mean(rs) / np.std(rs), 2) if np.std(rs) else 0.0,
    )


def main():
    if not mt5.initialize():
        print("MT5 init FAILED:", mt5.last_error()); return
    df = load(SYMBOL, TF, BARS)
    mt5.shutdown()
    if df.empty:
        print("Data yo'q"); return
    print(f"{SYMBOL} M15: {len(df)} bar  |  {df.index[0]} -> {df.index[-1]}")
    trades = backtest(df)
    if not trades:
        print("Savdo yo'q"); return

    print("\n=== YIL BO'YICHA (out-of-sample robustlik) ===")
    by_year = defaultdict(list)
    for t in trades:
        by_year[t["date"][:4]].append(t["r"])
    for yr in sorted(by_year):
        m = metrics(by_year[yr])
        print(f"  {yr}: n={m['n']:4d}  win={m['win']:5.1f}%  PF={m['pf']:<5}  "
              f"exp={m['exp']:+.3f}R  total={m['total_r']:+7.1f}R  DD={m['maxdd_r']:+.1f}R  Sharpe={m['sharpe']}")
    m = metrics([t["r"] for t in trades])
    print(f"\n  JAMI: n={m['n']}  win={m['win']}%  PF={m['pf']}  exp={m['exp']:+.3f}R  "
          f"total={m['total_r']:+.1f}R  DD={m['maxdd_r']}R  Sharpe={m['sharpe']}")

    # dataset saqlash (ML filtri uchun)
    import os
    os.makedirs("scratchpad", exist_ok=True)
    keys = sorted({k for t in trades for k in t})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader(); w.writerows(trades)
    print(f"\nDataset saqlandi: {OUT_CSV} ({len(trades)} savdo)")
    print("ESLATMA: 'ideal' bar-ijro + taxminiy spread. Real slippage biroz pastroq natija.")


if __name__ == "__main__":
    main()
