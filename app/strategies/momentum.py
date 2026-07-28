"""
TITAN AI — Momentum / EMA strategiyasi.

Manba: TITAN AI TRADING BIBLE, 21.10 (EMA Filter) va Momentum Strategy.
Tez va sekin EMA o'rtasidagi munosabat + qiyalik (slope) orqali trend kuchini
baholaydi. Fusion Engine'ga qo'shimcha ovoz sifatida qo'shiladi.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.constants import Direction


@dataclass
class MomentumResult:
    direction: Direction
    confidence: float
    reason: str


class MomentumStrategy:
    """EMA asosidagi momentum baholovchi."""

    def __init__(self, fast: int = 20, slow: int = 50, slope_lookback: int = 5) -> None:
        self.fast = fast
        self.slow = slow
        self.slope_lookback = slope_lookback

    def evaluate(self, df: pd.DataFrame) -> MomentumResult:
        if len(df) < self.slow + self.slope_lookback:
            return MomentumResult(Direction.WAIT, 0, "ma'lumot yetarli emas")

        close = df["close"]
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()

        f = ema_fast.iloc[-1]
        s = ema_slow.iloc[-1]
        slope = ema_fast.iloc[-1] - ema_fast.iloc[-1 - self.slope_lookback]

        # EMA ajralishini normallashtiramiz (o'rtacha shamga nisbatan)
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9
        separation = abs(f - s) / avg_range
        conf = min(90, 55 + separation * 20)

        if f > s and slope > 0:
            return MomentumResult(Direction.BUY, conf,
                                  f"EMA{self.fast}>EMA{self.slow} va yuqoriga qiyalik (momentum kuchli)")
        if f < s and slope < 0:
            return MomentumResult(Direction.SELL, conf,
                                  f"EMA{self.fast}<EMA{self.slow} va pastga qiyalik (momentum kuchli)")
        return MomentumResult(Direction.WAIT, 0, "EMA aralash — momentum aniq emas")
