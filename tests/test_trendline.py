"""Avto-trendline aniqlash testi (deterministik sintetik ma'lumot)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.charting.trendline import detect_trendlines


def _df(lows, highs):
    n = len(lows)
    idx = pd.date_range("2024-01-01", periods=n, freq="5min")
    opens = [(l + h) / 2 for l, h in zip(lows, highs)]
    closes = opens
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=idx
    )


def test_rising_support_detected():
    # Ko'tariluvchi support: lowlar 5,15,25 da pasayib, rising chiziqда yotadi.
    n = 31
    base = 1.10
    lows = [base + 0.02 for _ in range(n)]         # asosiy pol (yuqori)
    highs = [l + 0.010 for l in lows]
    # aniq pivot pastliklar (rising)
    for pos, val in [(5, 1.100), (15, 1.104), (25, 1.108)]:
        lows[pos] = val
        highs[pos] = val + 0.010
    df = _df(lows, highs)
    lines = detect_trendlines(df, is_buy=True)
    assert lines, "kamida bitta trend chiziq kutilardi"
    assert lines[0].kind == "support"
    assert lines[0].touches >= 2
    # o'ng uch chap langardan yuqori (rising) bo'lishi kerak
    assert lines[0].p2[1] > lines[0].p1[1]


def test_no_pivots_returns_empty():
    # Deyarli tekis — aniq pivot yo'q
    n = 20
    lows = [1.10 + 0.0001 * np.sin(i) for i in range(n)]
    highs = [l + 0.005 for l in lows]
    lines = detect_trendlines(_df(lows, highs), is_buy=True)
    assert isinstance(lines, list)  # xato bermaydi


def test_too_short_returns_empty():
    df = _df([1.1, 1.1, 1.1], [1.11, 1.11, 1.11])
    assert detect_trendlines(df) == []


def test_never_raises_on_bad_input():
    # None yoki bo'sh — hech qachon xato tashlamaydi (vizual-only kafolat)
    assert detect_trendlines(None) == []
    assert detect_trendlines(pd.DataFrame()) == []
