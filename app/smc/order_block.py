"""
TITAN AI — Order Block (OB) tahlili.

Manba: TITAN AI TRADING BIBLE, 3-bob.
Order Block — kuchli harakatdan (displacement) oldingi oxirgi qarama-qarshi sham:
  - Bullish OB: kuchli ko'tarilishdan oldingi oxirgi tushuvchi sham
  - Bearish OB: kuchli tushishdan oldingi oxirgi ko'taruvchi sham
Institutsional buyurtmalar shu zonada joylashgan deb hisoblanadi; narx qaytib
kelib bu zonadan "reaksiya" berishi mumkin.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.constants import Direction


@dataclass
class OrderBlock:
    """Bitta Order Block zonasi."""
    direction: Direction   # BUY (bullish) | SELL (bearish)
    top: float
    bottom: float
    index: int             # OB shami indeksi
    time: pd.Timestamp
    mitigated: bool = False  # narx qaytib zonaga kirdimi (kuchsizlangan)
    strength: float = 0.0    # displacement kuchi (necha marta o'rtacha range)

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class BreakerBlock:
    """
    Breaker Block — buzilgan Order Block.

    Order Block qarama-qarshi tomonga close bilan buzilsa, u qutbini almashtiradi:
      - Bullish OB (support) pastga buzilsa -> Bearish Breaker (resistance, SELL)
      - Bearish OB (resistance) yuqoriga buzilsa -> Bullish Breaker (support, BUY)
    Narx qaytib bu zonaga kelsa (retest), tez-tez kuchli reaksiya beradi.
    Manba: TITAN AI TRADING BIBLE, 3-bob (Breaker Block).
    """
    direction: Direction   # yangi (almashgan) yo'nalish
    top: float
    bottom: float
    index: int             # buzilish sodir bo'lgan sham indeksi
    time: pd.Timestamp
    retested: bool = False  # narx buzilishdan keyin zonaga qaytib keldimi

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


class OrderBlockAnalyzer:
    """
    Order Block zonalarini topadi.

    displacement_factor — impuls sham tanasi o'rtacha range'dan necha marta katta
    bo'lishi kerakligi (kuchli harakatni aniqlash uchun).
    """

    def __init__(self, displacement_factor: float = 1.5, lookback: int = 3) -> None:
        self.displacement_factor = displacement_factor
        self.lookback = lookback

    def find(self, df: pd.DataFrame) -> list[OrderBlock]:
        o = df["open"].to_numpy()
        h = df["high"].to_numpy()
        low = df["low"].to_numpy()
        c = df["close"].to_numpy()
        times = df.index
        n = len(df)

        body = abs(c - o)
        avg_body = float(body.mean()) or 1e-9

        blocks: list[OrderBlock] = []

        for i in range(1, n):
            is_strong = body[i] >= self.displacement_factor * avg_body
            if not is_strong:
                continue

            # Kuchli BULLISH impuls -> oldingi oxirgi bearish shamni topamiz
            if c[i] > o[i]:
                j = self._last_opposite(o, c, i, bearish=True)
                if j is not None:
                    blocks.append(
                        OrderBlock(
                            direction=Direction.BUY,
                            top=float(h[j]),
                            bottom=float(low[j]),
                            index=j,
                            time=times[j],
                            strength=round(body[i] / avg_body, 2),
                        )
                    )
            # Kuchli BEARISH impuls -> oldingi oxirgi bullish sham
            elif c[i] < o[i]:
                j = self._last_opposite(o, c, i, bearish=False)
                if j is not None:
                    blocks.append(
                        OrderBlock(
                            direction=Direction.SELL,
                            top=float(h[j]),
                            bottom=float(low[j]),
                            index=j,
                            time=times[j],
                            strength=round(body[i] / avg_body, 2),
                        )
                    )

        self._mark_mitigated(df, blocks)
        return blocks

    def _last_opposite(self, o, c, i: int, bearish: bool) -> int | None:
        """i shamidan oldingi oxirgi qarama-qarshi rangli shamni topadi."""
        start = max(0, i - self.lookback)
        for j in range(i - 1, start - 1, -1):
            if bearish and c[j] < o[j]:   # bearish sham qidiryapmiz
                return j
            if not bearish and c[j] > o[j]:  # bullish sham
                return j
        return None

    def _mark_mitigated(self, df: pd.DataFrame, blocks: list[OrderBlock]) -> None:
        """OB yaratilgandan keyin narx zonaga qaytib kirgan bo'lsa mitigated=True."""
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        for b in blocks:
            fut_h = highs[b.index + 1 :]
            fut_l = lows[b.index + 1 :]
            if len(fut_h) == 0:
                continue
            touched = ((fut_l <= b.top) & (fut_h >= b.bottom)).any()
            b.mitigated = bool(touched)

    def fresh(self, df: pd.DataFrame) -> list[OrderBlock]:
        """Faqat hali sinalmagan (fresh) Order Block larni qaytaradi."""
        return [b for b in self.find(df) if not b.mitigated]

    # ------------------------------------------------------------------ #
    #  Breaker Block: qarama-qarshi tomonga buzilgan Order Block
    # ------------------------------------------------------------------ #
    def find_breakers(self, df: pd.DataFrame) -> list[BreakerBlock]:
        """
        Buzilgan Order Block larni (Breaker) qaytaradi.

        OB close bilan qarama-qarshi chegaradan o'tsa — qutbi almashadi:
          - Bullish OB pastga (close < bottom) buzilsa -> SELL breaker
          - Bearish OB yuqoriga (close > top) buzilsa   -> BUY breaker
        """
        closes = df["close"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        times = df.index
        breakers: list[BreakerBlock] = []

        for b in self.find(df):
            fut = range(b.index + 1, len(df))
            break_idx: int | None = None
            for k in fut:
                if b.direction == Direction.BUY and closes[k] < b.bottom:
                    break_idx = k
                    break
                if b.direction == Direction.SELL and closes[k] > b.top:
                    break_idx = k
                    break
            if break_idx is None:
                continue

            flipped = Direction.SELL if b.direction == Direction.BUY else Direction.BUY
            # buzilishdan keyin narx zonaga qaytib keldimi (retest)?
            retested = False
            for k in range(break_idx + 1, len(df)):
                if lows[k] <= b.top and highs[k] >= b.bottom:
                    retested = True
                    break
            breakers.append(
                BreakerBlock(
                    direction=flipped,
                    top=b.top,
                    bottom=b.bottom,
                    index=break_idx,
                    time=times[break_idx],
                    retested=retested,
                )
            )
        return breakers
