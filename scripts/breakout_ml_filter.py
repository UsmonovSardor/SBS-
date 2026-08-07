"""
Gold breakout — ML FILTR (walk-forward, halol OOS).

breakout_dataset.csv (575 savdo) ustida: har breakout savdosi belgilaridan
P(win) bashorat qilib, past-ehtimolli savdolarni FILTRLAB, expectancy oshadimi
tekshiradi. TimeSeriesSplit (o'tmishda o'rgatib, kelajakda test) — look-ahead yo'q.

MUHIM (halol): filtr expectancy'ni faqat OOS'da barqaror oshirsagina qadrli.
Chegara TRAIN'da tanlanadi, TEST'ga qo'llanadi (post-hoc emas). Kichik namuna
(575) => ehtiyotkor xulosa.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

CSV = "scratchpad/breakout_dataset.csv"
FEATURES = ["range_atr", "hour", "dow", "atr", "prev_day_ret", "break_dist_atr", "sl_dist", "dir_buy"]


def expectancy(r):
    return (sum(r) / len(r)) if len(r) else 0.0


def wr(r):
    return 100 * sum(1 for x in r if x > 0) / len(r) if len(r) else 0.0


def main():
    df = pd.read_csv(CSV).sort_values("date").reset_index(drop=True)
    df["dir_buy"] = (df["dir"] == "BUY").astype(int)
    X = df[FEATURES].values
    y = df["won"].values
    r = df["r"].values
    n = len(df)
    print(f"Dataset: {n} savdo | baza expectancy={expectancy(r):+.3f}R  win={wr(r):.1f}%")

    models = {
        "GradBoost(d2)": lambda: GradientBoostingClassifier(max_depth=2, n_estimators=120, learning_rate=0.05, subsample=0.8, random_state=1),
        "Logistic":      lambda: LogisticRegression(max_iter=1000, C=0.5),
    }

    tss = TimeSeriesSplit(n_splits=5)
    for mname, mk in models.items():
        oos_proba = np.full(n, np.nan)
        oos_thr_keep = np.zeros(n, dtype=bool)  # TRAIN'da tanlangan chegara bo'yicha
        for tr_idx, te_idx in tss.split(X):
            scaler = StandardScaler().fit(X[tr_idx])
            Xtr, Xte = scaler.transform(X[tr_idx]), scaler.transform(X[te_idx])
            m = mk().fit(Xtr, y[tr_idx])
            p_tr = m.predict_proba(Xtr)[:, 1]
            p_te = m.predict_proba(Xte)[:, 1]
            oos_proba[te_idx] = p_te
            # chegara: TRAIN'da yuqori 60% ehtimolni saqla (median-usti)
            thr = np.quantile(p_tr, 0.40)
            oos_thr_keep[te_idx] = p_te >= thr

        mask = ~np.isnan(oos_proba)
        rr = r[mask]
        pr = oos_proba[mask]
        keep_honest = oos_thr_keep[mask]

        print(f"\n=== {mname} (OOS n={mask.sum()}) ===")
        print(f"  BAZA (filtrsiz):     n={len(rr):4d}  win={wr(rr):5.1f}%  exp={expectancy(rr):+.3f}R")
        rk = rr[keep_honest]
        print(f"  HALOL FILTR (train-chegara): n={len(rk):4d}  win={wr(rk):5.1f}%  exp={expectancy(rk):+.3f}R  "
              f"(saqlangan {100*len(rk)/len(rr):.0f}%)")
        # chegara supi (ma'lumot uchun — post-hoc, optimistik)
        print("  chegara sweep (post-hoc, optimistik — faqat ma'lumot):")
        for q in [0.3, 0.5, 0.7]:
            thr = np.quantile(pr, q)
            sel = pr >= thr
            print(f"    p>=Q{int(q*100)}={thr:.2f}: n={sel.sum():4d}  win={wr(rr[sel]):5.1f}%  exp={expectancy(rr[sel]):+.3f}R")

    # Feature muhimligi (butun datada, ma'lumot uchun)
    scaler = StandardScaler().fit(X)
    gb = GradientBoostingClassifier(max_depth=2, n_estimators=120, learning_rate=0.05, random_state=1).fit(scaler.transform(X), y)
    print("\n=== Feature muhimligi (GradBoost, butun data) ===")
    for f, imp in sorted(zip(FEATURES, gb.feature_importances_), key=lambda t: -t[1]):
        print(f"  {f:16} {imp:.3f}")
    print("\nESLATMA: 575 savdo ML uchun KICHIK. HALOL FILTR bazadan barqaror "
          "yuqori bo'lsagina qadrli; aks holda overfit.")


if __name__ == "__main__":
    main()
