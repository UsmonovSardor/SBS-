"""
TITAN AI — Fair Value Gap (FVG) tahlili.

Manba: TITAN AI TRADING BIBLE, 4-bob.
FVG — uch shamli bo'shliq (imbalance):
  - Bullish FVG: 1-sham HIGH < 3-sham LOW  (pastda bo'shliq, narx qaytib to'ldirishi mumkin)
  - Bearish FVG: 1-sham LOW  > 3-sham HIGH (yuqorida bo'shliq)
Agar keyingi narx bo'shliqqa kirsa — "filled" (to'ldirilgan) deb belgilanadi.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.constants import Direction


@dataclass
class FVG:
    """Bitta Fair Value Gap zonasi."""
    direction: Direction   # BUY (bullish) | SELL (bearish)
    top: float             # zona yuqori chegarasi
    bottom: float          # zona pastki chegarasi
    index: int             # o'rtadagi (3-chi) sham indeksi
    time: pd.Timestamp
    filled: bool = False   # keyin narx bu zonaga kirdimi
    size: float = 0.0      # zona balandligi (top - bottom)

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


class FVGAnalyzer:
    """Fair Value Gap zonalarini topadi."""

    def __init__(self, min_size_ratio: float = 0.0) -> None:
        # min_size_ratio — juda kichik bo'shliqlarni e'tiborsiz qoldirish uchun
        # (0 = hammasi hisobga olinadi)
        self.min_size_ratio = min_size_ratio

    def find(self, df: pd.DataFrame) -> list[FVG]:
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        times = df.index
        n = len(df)

        gaps: list[FVG] = []
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9

        # i — uchlikning o'rtangi (3-chi) shami; i-2, i-1, i
        for i in range(2, n):
            c1_high, c1_low = highs[i - 2], lows[i - 2]
            c3_high, c3_low = highs[i], lows[i]

            # Bullish FVG: 1-sham high < 3-sham low
            if c1_high < c3_low:
                top, bottom = c3_low, c1_high
                size = top - bottom
                if size >= self.min_size_ratio * avg_range:
                    gaps.append(
                        FVG(
                            direction=Direction.BUY,
                            top=float(top),
                            bottom=float(bottom),
                            index=i,
                            time=times[i],
                            size=float(size),
                        )
                    )

            # Bearish FVG: 1-sham low > 3-sham high
            elif c1_low > c3_high:
                top, bottom = c1_low, c3_high
                size = top - bottom
                if size >= self.min_size_ratio * avg_range:
                    gaps.append(
                        FVG(
                            direction=Direction.SELL,
                            top=float(top),
                            bottom=float(bottom),
                            index=i,
                            time=times[i],
                            size=float(size),
                        )
                    )

        self._mark_filled(df, gaps)
        return gaps

    def _mark_filled(self, df: pd.DataFrame, gaps: list[FVG]) -> None:
        """Zona yaratilgandan keyin narx unga kirgan bo'lsa filled=True."""
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        for g in gaps:
            future_high = highs[g.index + 1 :]
            future_low = lows[g.index + 1 :]
            if len(future_high) == 0:
                continue
            # narx zonaga tegdimi?
            touched = ((future_low <= g.top) & (future_high >= g.bottom)).any()
            g.filled = bool(touched)

    def fresh(self, df: pd.DataFrame) -> list[FVG]:
        """Faqat to'ldirilmagan (fresh) FVG larni qaytaradi."""
        return [g for g in self.find(df) if not g.filled]
