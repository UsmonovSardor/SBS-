"""
TITAN AI — Avtomatik trend liniya (trendline) aniqlash.

MUHIM: bu modul FAQAT VIZUAL — grafikда chiroyli trend chizig'ini ko'rsatadi,
signal/fusion mantig'ига UMUMAN TEGMAYDI (edge o'zgarmaydi). Qo'lда chizilган
TradingView chiziqlarini hech narsa o'qiy olmaydi, shuning uchun chiziq pivot
(swing) nuqtalar asosида KOD bilan avtomatik aniqlanadi.

Mantiq (klassik):
  - support liniya (ko'tarilish): oxirgi 2 swing LOW ni tutashtiradi, chiziq
    narx ostида qolishi (buzilmasligi) tekshiriladi, o'ngга (joriy sham) cho'ziladi.
  - resistance liniya (tushish): oxirgi 2 swing HIGH bilan aksincha.
Yaroqsiz (buzilган) chiziq QAYTARILMAYDI — noto'g'ri chiziqдан ko'ra yo'q afzal.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.smc.structure import StructureAnalyzer


@dataclass
class TrendLine:
    """Grafikда chiziladigan bitta trend liniya (2 nuqta, alines uchun tayyor)."""
    p1: tuple[pd.Timestamp, float]   # (vaqt, narx) — chap langar (eski pivot)
    p2: tuple[pd.Timestamp, float]   # (vaqt, narx) — o'ng uch (joriy shamга proyeksiya)
    kind: str                        # "support" | "resistance"
    touches: int                     # chiziqqa tegган pivotlar soni (>=2)


def _fit_line(swings, n, prices, idx, tol, kind, side) -> TrendLine | None:
    """Oxirgi 2 pivotдан chiziq quradi; buzilган bo'lsa None qaytaradi.
    side: 'below' (support — narx chiziq ustida turishi kerak) yoki
          'above' (resistance — narx chiziq ostida turishi kerak)."""
    if len(swings) < 2:
        return None
    p_prev, p_last = swings[-2], swings[-1]
    if p_last.index == p_prev.index:
        return None

    m = (p_last.price - p_prev.price) / (p_last.index - p_prev.index)  # qiyalik
    b = p_prev.price - m * p_prev.index                                # y = m*x + b

    # Buzilish tekshiruvi: p_prev dan joriy shamgacha narx chiziqdan tol dan
    # ortiq o'tib ketmasligi kerak (aks holda chiziq yaroqsiz).
    for i in range(p_prev.index, n):
        line_y = m * i + b
        if side == "below" and prices[i] < line_y - tol:
            return None
        if side == "above" and prices[i] > line_y + tol:
            return None

    # Tegishlar (pivotlar) sonini sanaymiz — kamida 2 (ikkala langar).
    touches = 0
    for s in swings:
        if s.index < p_prev.index:
            continue
        if abs(s.price - (m * s.index + b)) <= tol:
            touches += 1

    last_i = n - 1
    y_end = m * last_i + b
    return TrendLine(
        p1=(idx[p_prev.index], float(p_prev.price)),
        p2=(idx[last_i], float(y_end)),
        kind=kind,
        touches=int(touches),
    )


def detect_trendlines(
    df: pd.DataFrame,
    is_buy: bool | None = None,
    lookback: int = 2,
    tol_ratio: float = 0.6,
    min_touches: int = 2,
    max_lines: int = 2,
) -> list[TrendLine]:
    """df (ko'rinadigan shamlar) uchun trend liniyalarni qaytaradi.
    is_buy — signal yo'nalishi (mos chiziq birinchi tartibда). Xato/yetarli
    ma'lumot yo'q bo'lsa bo'sh ro'yxat (grafik avvalgidek chiziladi)."""
    try:
        if df is None or len(df) < (2 * lookback + 5):
            return []
        analyzer = StructureAnalyzer(lookback=lookback)
        highs_sw, lows_sw = analyzer.find_swings(df)
        n = len(df)
        lows = df["low"].to_numpy()
        highs = df["high"].to_numpy()
        idx = df.index
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9
        tol = tol_ratio * avg_range

        support = _fit_line(lows_sw, n, lows, idx, tol, "support", "below")
        resistance = _fit_line(highs_sw, n, highs, idx, tol, "resistance", "above")

        # Signal yo'nalishiga mos chiziq birinchi
        if is_buy is False:
            ordered = [resistance, support]
        else:  # BUY yoki noma'lum -> support birinchi
            ordered = [support, resistance]

        out: list[TrendLine] = []
        for ln in ordered:
            if ln is not None and ln.touches >= min_touches:
                out.append(ln)
            if len(out) >= max_lines:
                break
        return out
    except Exception:  # noqa: BLE001 — vizual funksiya hech qachon grafikni buzmasin
        return []
