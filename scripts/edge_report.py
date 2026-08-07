"""
TITAN AI — Edge hisoboti (data-asosli o'lchov).

Jonli jurnal (titan.db) dagi signal + natija (tracked) + belgilar (signal_votes)
ni birlashtirib, HALOL expectancy tahlilini beradi:
  - umumiy expectancy (o'rtacha R/signal), win-rate, gross R
  - kesimlar: simvol / timeframe / yo'nalish / soat / confidence / strength
  - belgi (ovoz) tahlili: har strategiya FAOL bo'lganda natija farqi (edge signali)

MUHIM: bu FAQAT O'LCHOV — signal mantig'iga tegmaydi. Maqsad: edge bor-yo'qligini
va (bo'lsa) QAYERDA ekanini raqam bilan ko'rish. Kam namunada xulosa ehtiyotkor.

Ishlatish (konteynerда):  python /tmp/edge_report.py
Yoki lokal nusxa:          python scripts/edge_report.py --db data/titan.db
"""
from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict

# Natija -> R (tracker semantikasi bilan mos)
def result_to_r(result: str) -> float | None:
    if not result:
        return None
    if result.startswith("TP3"):
        return 3.0
    if result.startswith("TP1"):   # "TP1'da qulflandi (+1R)"
        return 1.0
    if result.startswith("Breakeven"):
        return 0.0
    if result.startswith("SL"):
        return -1.0
    return None  # Duplikat / Muddati tugadi / boshqa -> tahlildan tashqari


def _fmt(n, wr, exp, gross):
    return f"n={n:4d}  win={wr:5.1f}%  exp={exp:+.3f}R  gross={gross:+6.1f}R"


def _stats(rows):
    """rows: list of R -> (n, winrate%, expectancy, grossR)."""
    n = len(rows)
    if n == 0:
        return 0, 0.0, 0.0, 0.0
    wins = sum(1 for r in rows if r > 0)
    gross = sum(rows)
    return n, 100.0 * wins / n, gross / n, gross


def main(db_path: str) -> None:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row

    # 1) signal + natija (created_at == opened_at)
    base = c.execute("""
        SELECT s.id, s.symbol, s.timeframe, s.direction, s.confidence, s.strength,
               s.created_at, t.result
        FROM signals s
        JOIN tracked_signals t ON s.created_at = t.opened_at
        WHERE t.status='CLOSED'
    """).fetchall()

    records = []
    for r in base:
        R = result_to_r(r["result"])
        if R is None:
            continue
        hour = (r["created_at"] or "T")[11:13]
        records.append({
            "id": r["id"], "symbol": r["symbol"], "tf": r["timeframe"],
            "dir": r["direction"], "conf": r["confidence"] or 0,
            "strength": r["strength"], "hour": hour, "R": R,
        })

    allR = [x["R"] for x in records]
    print("=" * 60)
    print("  TITAN AI — EDGE HISOBOTI (jonli jurnal)")
    print("=" * 60)
    print("UMUMIY:", _fmt(*_stats(allR)))
    print("  (exp>0 = foydali; exp<0 = zararli. Win-rate yolg'iz ma'nosiz —")
    print("   Breakeven 0R 'yutuq emas' deb sanaladi.)")

    def breakdown(title, keyfn, sort_by_n=True):
        print(f"\n--- {title} ---")
        groups = defaultdict(list)
        for x in records:
            groups[keyfn(x)].append(x["R"])
        items = sorted(groups.items(),
                       key=lambda kv: (-len(kv[1]) if sort_by_n else kv[0]))
        for k, rs in items:
            n, wr, exp, gross = _stats(rs)
            if n < 3:
                continue  # juda kam namuna — o'tkazamiz
            print(f"  {str(k):10} {_fmt(n, wr, exp, gross)}")

    breakdown("SIMVOL", lambda x: x["symbol"])
    breakdown("TIMEFRAME", lambda x: x["tf"])
    breakdown("YO'NALISH", lambda x: x["dir"])
    breakdown("SOAT (UTC)", lambda x: x["hour"], sort_by_n=False)

    def conf_bucket(cf):
        cf = float(cf)
        if cf < 65: return "60-64%"
        if cf < 70: return "65-69%"
        if cf < 75: return "70-74%"
        if cf < 80: return "75-79%"
        return "80%+"
    breakdown("CONFIDENCE", lambda x: conf_bucket(x["conf"]), sort_by_n=False)
    breakdown("STRENGTH", lambda x: x["strength"], sort_by_n=False)

    # 2) Belgi (ovoz) tahlili — strategiya FAOL (signal yo'nalishida ovoz bergan)
    #    bo'lganda vs bermaganda natija farqi.
    print("\n--- OVOZ (BELGI) TAHLILI: strategiya signal yo'nalishida FAOL bo'lsa ---")
    votes = c.execute("SELECT signal_id, strategy, direction FROM signal_votes").fetchall()
    vote_by_sig = defaultdict(dict)
    for v in votes:
        vote_by_sig[v["signal_id"]][v["strategy"]] = v["direction"]

    rec_by_id = {x["id"]: x for x in records}
    strategies = sorted({v["strategy"] for v in votes})
    if not vote_by_sig:
        print("  (signal_votes bo'sh — feature-logging'dan keyingi data yo'q)")
    else:
        for strat in strategies:
            active, inactive = [], []
            for sid, sv in vote_by_sig.items():
                rec = rec_by_id.get(sid)
                if rec is None:
                    continue
                if sv.get(strat) == rec["dir"]:
                    active.append(rec["R"])
                else:
                    inactive.append(rec["R"])
            na, _, ea, _ = _stats(active)
            ni, _, ei, _ = _stats(inactive)
            if na >= 3 and ni >= 3:
                edge = ea - ei
                flag = "  <-- ijobiy farq" if edge > 0.1 else ""
                print(f"  {strat:16} FAOL: exp={ea:+.3f}R(n={na})  "
                      f"NOFAOL: exp={ei:+.3f}R(n={ni})  farq={edge:+.3f}R{flag}")

    print("\n" + "=" * 60)
    print(f"  Jami tahlil qilingan natija: {len(records)}")
    print("  ESLATMA: <500 namuna = statistik ISHONCHSIZ. Bu boshlang'ich")
    print("  o'lchov; asosiy xulosa keng backtest datasetда chiqadi (Faza 1).")
    print("=" * 60)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/app/data/titan.db")
    main(ap.parse_args().db)
