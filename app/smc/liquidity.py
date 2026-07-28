"""
TITAN AI — Liquidity (likvidlik) tahlili.

Manba: TITAN AI TRADING BIBLE, 2 va 8-boblar.
  - Equal High / Equal Low: bir xil darajadagi swing nuqtalar — u yerda
    trader'larning stop-loss'lari (likvidlik) to'plangan.
  - Liquidity Sweep: narx shu darajadan o'tib (likvidlikni "yig'ib"), keyin
    qaytib yopiladi — bu ko'pincha teskari harakat (reversal) signali.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.constants import Direction
from app.smc.structure import StructureAnalyzer, SwingPoint


@dataclass
class LiquidityPool:
    """Bir xil darajadagi swing nuqtalar to'plami (likvidlik zonasi)."""
    kind: str                # "equal_high" | "equal_low"
    price: float
    points: list[SwingPoint] = field(default_factory=list)
    swept: bool = False      # bu daraja yig'ib olindimi


@dataclass
class LiquiditySweep:
    """Likvidlik yig'ish hodisasi (sweep)."""
    direction: Direction     # SELL (highs yig'ildi) | BUY (lows yig'ildi)
    level: float             # yig'ilgan daraja
    index: int
    time: pd.Timestamp


class LiquidityAnalyzer:
    """Equal High/Low zonalarini va Sweep hodisalarini topadi."""

    def __init__(self, lookback: int = 2, tolerance_ratio: float = 0.1) -> None:
        # tolerance_ratio — "bir xil" deb hisoblash uchun o'rtacha range ulushi
        self.structure = StructureAnalyzer(lookback=lookback)
        self.tolerance_ratio = tolerance_ratio

    def analyze(self, df: pd.DataFrame) -> tuple[list[LiquidityPool], list[LiquiditySweep]]:
        swing_highs, swing_lows = self.structure.find_swings(df)
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9
        tol = self.tolerance_ratio * avg_range

        pools = self._find_equal_levels(swing_highs, "equal_high", tol) + self._find_equal_levels(
            swing_lows, "equal_low", tol
        )
        sweeps = self._detect_sweeps(df, pools)
        return pools, sweeps

    def _find_equal_levels(
        self, swings: list[SwingPoint], kind: str, tol: float
    ) -> list[LiquidityPool]:
        """Bir-biriga yaqin (tol ichida) swing nuqtalarni guruhlaydi."""
        pools: list[LiquidityPool] = []
        used = [False] * len(swings)

        for i in range(len(swings)):
            if used[i]:
                continue
            group = [swings[i]]
            used[i] = True
            for j in range(i + 1, len(swings)):
                if used[j]:
                    continue
                if abs(swings[j].price - swings[i].price) <= tol:
                    group.append(swings[j])
                    used[j] = True
            # kamida 2 ta nuqta bo'lsa — "equal" hisoblanadi
            if len(group) >= 2:
                avg_price = sum(p.price for p in group) / len(group)
                pools.append(LiquidityPool(kind=kind, price=float(avg_price), points=group))

        return pools

    def _detect_sweeps(
        self, df: pd.DataFrame, pools: list[LiquidityPool]
    ) -> list[LiquiditySweep]:
        """
        Narx equal darajadan wick bilan o'tib, close bilan qaytib kirsa — sweep.
        """
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        times = df.index
        sweeps: list[LiquiditySweep] = []

        for pool in pools:
            # pool oxirgi nuqtasidan keyingi shamlarni tekshiramiz
            last_idx = max(p.index for p in pool.points)
            for i in range(last_idx + 1, len(df)):
                if pool.kind == "equal_high":
                    # wick daraja ustidan o'tdi, lekin close pastda yopildi
                    if highs[i] > pool.price and closes[i] < pool.price:
                        pool.swept = True
                        sweeps.append(
                            LiquiditySweep(
                                direction=Direction.SELL,
                                level=pool.price,
                                index=i,
                                time=times[i],
                            )
                        )
                        break
                else:  # equal_low
                    if lows[i] < pool.price and closes[i] > pool.price:
                        pool.swept = True
                        sweeps.append(
                            LiquiditySweep(
                                direction=Direction.BUY,
                                level=pool.price,
                                index=i,
                                time=times[i],
                            )
                        )
                        break

        return sweeps
