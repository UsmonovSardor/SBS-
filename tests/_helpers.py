"""Testlar uchun sintetik OHLC DataFrame quruvchi yordamchilar (MT5 kerak emas)."""
from __future__ import annotations

import pandas as pd


def make_df(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """bars = [(open, high, low, close), ...] -> DatetimeIndex li DataFrame."""
    idx = pd.date_range("2024-01-01", periods=len(bars), freq="15min")
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)


def bars_from_closes(
    closes: list[float], wick: float = 0.05
) -> list[tuple[float, float, float, float]]:
    """Close qiymatlaridan OHLC shamlar yasaydi (open = oldingi close)."""
    bars: list[tuple[float, float, float, float]] = []
    prev = closes[0]
    for c in closes:
        o = prev
        hi = max(o, c) + wick
        lo = min(o, c) - wick
        bars.append((o, hi, lo, c))
        prev = c
    return bars


def zigzag(pivots: list[float], steps: int = 4) -> list[float]:
    """Pivotlar orasini chiziqli to'ldirib zigzag close ketma-ketligini yasaydi."""
    closes = [float(pivots[0])]
    for a, b in zip(pivots, pivots[1:]):
        for s in range(1, steps + 1):
            closes.append(a + (b - a) * s / steps)
    return closes


def df_from_closes(closes: list[float], wick: float = 0.05) -> pd.DataFrame:
    return make_df(bars_from_closes(closes, wick=wick))
