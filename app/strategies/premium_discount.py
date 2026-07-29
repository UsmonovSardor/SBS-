"""
TITAN AI — Premium / Discount (Equilibrium) strategiyasi.

Manba: TITAN AI TRADING BIBLE, 34-bob (SMC) — Premium/Discount.
Joriy "dealing range" (oxirgi swing high–low) ning o'rtasi = equilibrium (50%).
Institutsional yondashuv:
  - Faqat DISCOUNT zonada (narx 50% dan past) BUY qilinadi — "arzon".
  - Faqat PREMIUM zonada (narx 50% dan yuqori) SELL qilinadi — "qimmat".
  - Equilibrium atrofida (~50%) aniq bias yo'q -> WAIT.
Fusion Engine'ga qo'shimcha ovoz/filtr sifatida qo'shiladi.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.constants import Direction


@dataclass
class PremiumDiscountResult:
    direction: Direction
    confidence: float
    reason: str
    position: float  # narxning range ichidagi o'rni (0=low, 1=high)


class PremiumDiscountStrategy:
    """Dealing range ichidagi equilibriumga qarab premium/discount baholaydi."""

    def __init__(self, window: int = 50, neutral_band: float = 0.05) -> None:
        # window — dealing range hisoblanadigan oxirgi shamlar soni
        # neutral_band — equilibrium atrofidagi "bias yo'q" zona (±)
        self.window = window
        self.neutral_band = neutral_band

    def evaluate(self, df: pd.DataFrame) -> PremiumDiscountResult:
        if len(df) < 5:
            return PremiumDiscountResult(Direction.WAIT, 0, "ma'lumot yetarli emas", 0.5)

        recent = df.iloc[-self.window :]
        hi = float(recent["high"].max())
        lo = float(recent["low"].min())
        rng = hi - lo
        if rng <= 0:
            return PremiumDiscountResult(Direction.WAIT, 0, "range yo'q (tekis bozor)", 0.5)

        price = float(df["close"].iloc[-1])
        pos = (price - lo) / rng            # 0 = eng past, 1 = eng baland
        pos = max(0.0, min(1.0, pos))

        # Equilibrium atrofida — aniq bias yo'q
        if abs(pos - 0.5) <= self.neutral_band:
            return PremiumDiscountResult(
                Direction.WAIT, 0, f"equilibrium atrofida (pos={pos:.0%})", pos
            )

        # Chegaradan uzoqlashgan sari ishonch ortadi (55 -> 90)
        depth = abs(pos - 0.5) / 0.5        # 0..1
        conf = round(min(90.0, 55 + depth * 35), 1)

        if pos < 0.5:  # DISCOUNT -> BUY
            return PremiumDiscountResult(
                Direction.BUY, conf, f"discount zonada (pos={pos:.0%}) — arzon, BUY foydali", pos
            )
        # PREMIUM -> SELL
        return PremiumDiscountResult(
            Direction.SELL, conf, f"premium zonada (pos={pos:.0%}) — qimmat, SELL foydali", pos
        )
