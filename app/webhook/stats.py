"""
TITAN AI — statistika hisoblagichi (dashboard uchun).

Jurnal `data/titan.db` dan (READ-ONLY, bot yozuviga xalaqit bermaydi) to'liq
statistika hisoblaydi. tracked_signals.result -> R-multiplikator:
  SL -1R | Breakeven 0R | TP1 +1R | TP3 +3R | (Muddati/Duplikat/ochiq = chetlatiladi).

FAQAT o'qiydi — hech narsa o'zgartirmaydi. Webhook (tvhook) xizmati ishlatadi.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.core.config import BASE_DIR

DB_PATH = BASE_DIR / "data" / "titan.db"
UZ_OFFSET = timedelta(hours=5)   # Toshkent = UTC+5 (yil bo'yi, DST yo'q)


def _uz(iso: str | None) -> str:
    """Konteyner (UTC) ISO vaqtini Toshkent vaqtiga o'giradi: '2026-08-10 17:07'."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:16]
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return (dt + UZ_OFFSET).strftime("%Y-%m-%d %H:%M")


def _now_uz() -> str:
    return (datetime.now(timezone.utc).replace(tzinfo=None) + UZ_OFFSET).strftime("%Y-%m-%d %H:%M")


def _r(result: str | None) -> float | None:
    """result matnini R-multiplikatorga o'giradi (chetlatilsa None)."""
    if not result:
        return None
    if "Duplikat" in result or "Muddati" in result:
        return None                      # toza natija emas — chetlatiladi
    if "Stop Loss" in result:
        return -1.0
    # DIQQAT: "Breakeven (TP1 dan keyin...)" matnida "TP1" bor — Breakeven'ni
    # TP1/TP3 dan OLDIN tekshirish shart, aks holda 0R xato +1R sanaladi.
    if "Breakeven" in result:
        return 0.0
    if "TP3" in result:
        return 3.0
    if "TP1" in result:
        return 1.0
    return None


def _agg(rows, key):
    """key bo'yicha guruhlab n/expectancy/total_r/win_rate."""
    g: dict[str, list[float]] = {}
    for row in rows:
        g.setdefault(row[key], []).append(row["r"])
    out = []
    for k, rs in g.items():
        n = len(rs)
        wins = sum(1 for x in rs if x > 0)
        losses = sum(1 for x in rs if x < 0)
        wr = round(100 * wins / (wins + losses), 1) if (wins + losses) else 0.0
        out.append({
            "key": k, "n": n,
            "exp": round(sum(rs) / n, 3) if n else 0.0,
            "total_r": round(sum(rs), 1),
            "win_rate": wr,
        })
    return sorted(out, key=lambda d: -d["n"])


def compute_stats() -> dict:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        def count(sql: str) -> int:
            try:
                return conn.execute(sql).fetchone()[0]
            except sqlite3.OperationalError:
                return 0

        signals_total = count("SELECT COUNT(*) FROM signals")
        executed = count("SELECT COUNT(*) FROM trades")
        open_n = count("SELECT COUNT(*) FROM tracked_signals WHERE status='OPEN'")

        if "tracked_signals" not in tables:
            return {
                "generated_at": _now_uz(),
                "kpi": {"signals_total": signals_total, "executed": executed,
                        "resolved": 0, "open": 0, "wins": 0, "losses": 0, "breakeven": 0,
                        "win_rate": 0.0, "expectancy": 0.0, "profit_factor": 0.0,
                        "total_r": 0.0, "max_dd_r": 0.0},
                "result_dist": {}, "by_symbol": [], "by_direction": [], "by_tf": [],
                "equity": [], "recent": [],
            }

        tr = conn.execute(
            """SELECT symbol, timeframe, direction, result, opened_at, closed_at
               FROM tracked_signals WHERE status='CLOSED' ORDER BY closed_at""").fetchall()

        # R bilan boyitilgan toza natijalar
        resolved = []
        result_dist: dict[str, int] = {}
        for row in tr:
            res = row["result"] or ""
            short = ("SL" if "Stop Loss" in res else
                     "Breakeven" if "Breakeven" in res else   # TP1'dan OLDIN (matnda "TP1" bor)
                     "TP3" if "TP3" in res else
                     "TP1" if "TP1" in res else
                     "Muddati" if "Muddati" in res else
                     "Duplikat" if "Duplikat" in res else "Boshqa")
            result_dist[short] = result_dist.get(short, 0) + 1
            r = _r(res)
            if r is None:
                continue
            resolved.append({
                "symbol": row["symbol"], "timeframe": row["timeframe"],
                "direction": row["direction"], "r": r,
                "closed_at": row["closed_at"], "opened_at": row["opened_at"],
                "result": short,
            })

        n = len(resolved)
        wins = sum(1 for x in resolved if x["r"] > 0)
        losses = sum(1 for x in resolved if x["r"] < 0)
        be = sum(1 for x in resolved if x["r"] == 0)
        total_r = sum(x["r"] for x in resolved)
        gross_w = sum(x["r"] for x in resolved if x["r"] > 0)
        gross_l = abs(sum(x["r"] for x in resolved if x["r"] < 0))
        exp = round(total_r / n, 3) if n else 0.0
        wr = round(100 * wins / (wins + losses), 1) if (wins + losses) else 0.0
        pf = round(gross_w / gross_l, 2) if gross_l else (float("inf") if gross_w else 0.0)

        # equity egri (kümülativ R)
        cum = 0.0
        equity = []
        for i, x in enumerate(resolved, 1):
            cum += x["r"]
            equity.append({"i": i, "t": _uz(x["closed_at"]), "cum": round(cum, 2)})
        # max drawdown (R)
        peak = 0.0
        maxdd = 0.0
        c = 0.0
        for x in resolved:
            c += x["r"]
            peak = max(peak, c)
            maxdd = min(maxdd, c - peak)

        recent = [{
            "t": _uz(x["closed_at"] or x["opened_at"]),
            "symbol": x["symbol"], "tf": x["timeframe"],
            "dir": x["direction"], "result": x["result"], "r": x["r"],
        } for x in reversed(resolved)][:15]

        return {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "kpi": {
                "signals_total": signals_total, "executed": executed,
                "resolved": n, "open": open_n,
                "wins": wins, "losses": losses, "breakeven": be,
                "win_rate": wr, "expectancy": exp, "profit_factor": pf,
                "total_r": round(total_r, 1), "max_dd_r": round(maxdd, 1),
            },
            "result_dist": result_dist,
            "by_symbol": _agg(resolved, "symbol"),
            "by_direction": _agg(resolved, "direction"),
            "by_tf": _agg(resolved, "timeframe"),
            "equity": equity,
            "recent": recent,
        }
    finally:
        conn.close()
