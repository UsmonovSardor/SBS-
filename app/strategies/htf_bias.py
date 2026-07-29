"""
TITAN AI — Higher-Timeframe (HTF) Bias / Multi-Timeframe konfluens.

Manba: TITAN AI TRADING BIBLE, 6-bob (Multi-Timeframe AI Engine).
Institutsional qoida: past taymfrejmdagi savdo yuqori taymfrejm trendi bilan
bir yo'nalishда bo'lishi kerak ("trade with the higher-timeframe bias").
Bu modul yuqori TF shamlaridan trendni aniqlab, fusion'ga bias ovozini beradi.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.constants import Direction, Timeframe, Trend
from app.smc.structure import StructureAnalyzer

# Skan taymfrejmi -> mos keladigan yuqori taymfrejm (konfluens uchun)
HTF_MAP: dict[Timeframe, Timeframe] = {
    Timeframe.M1: Timeframe.M15,
    Timeframe.M5: Timeframe.H1,
    Timeframe.M15: Timeframe.H4,
    Timeframe.M30: Timeframe.H4,
    Timeframe.H1: Timeframe.H4,
    Timeframe.H4: Timeframe.D1,
    Timeframe.D1: Timeframe.W1,
}


def higher_timeframe(tf: Timeframe) -> Timeframe:
    """Berilgan taymfrejm uchun konfluens TF (yo'q bo'lsa — o'zini qaytaradi)."""
    return HTF_MAP.get(tf, tf)


@dataclass
class HtfBiasResult:
    direction: Direction
    confidence: float
    reason: str


class HtfBias:
    """Yuqori taymfrejm trendini bias ovoziga aylantiradi."""

    def __init__(self) -> None:
        self.structure = StructureAnalyzer()

    def evaluate(self, htf_df: pd.DataFrame | None) -> HtfBiasResult:
        if htf_df is None or len(htf_df) < 10:
            return HtfBiasResult(Direction.WAIT, 0, "HTF ma'lumoti yo'q")

        trend = self.structure.analyze(htf_df).trend
        if trend == Trend.BULLISH:
            return HtfBiasResult(Direction.BUY, 80, "HTF trend yuqoriga (bias BUY)")
        if trend == Trend.BEARISH:
            return HtfBiasResult(Direction.SELL, 80, "HTF trend pastga (bias SELL)")
        return HtfBiasResult(Direction.WAIT, 0, "HTF trend aniq emas (range)")
