"""
TITAN AI — Market Structure (bozor tuzilishi) tahlili.

Manba: TITAN AI TRADING BIBLE, 1-bob.
Aniqlaydi:
  - Swing High / Swing Low (cho'qqi va tublar)
  - Trend: BULLISH (HH+HL) / BEARISH (LH+LL) / RANGE
  - BOS  (Break of Structure)   — trend davomi signali
  - CHoCH (Change of Character)  — trend o'zgarishi signali
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.constants import Direction, Trend


@dataclass
class SwingPoint:
    """Bitta swing nuqta (cho'qqi yoki tub)."""
    index: int
    time: pd.Timestamp
    price: float
    kind: str  # "high" | "low"


@dataclass
class StructureEvent:
    """Struktura hodisasi (BOS yoki CHoCH)."""
    kind: str            # "BOS" | "CHOCH"
    direction: Direction  # BUY (bullish) | SELL (bearish)
    price: float          # buzilgan swing narxi
    time: pd.Timestamp    # buzilgan sham vaqti
    broken_swing: float   # buzilgan swing nuqta narxi


@dataclass
class StructureResult:
    """Market Structure tahlili natijasi."""
    trend: Trend
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows: list[SwingPoint] = field(default_factory=list)
    events: list[StructureEvent] = field(default_factory=list)

    @property
    def last_event(self) -> StructureEvent | None:
        return self.events[-1] if self.events else None

    @property
    def last_bos(self) -> StructureEvent | None:
        for ev in reversed(self.events):
            if ev.kind == "BOS":
                return ev
        return None

    @property
    def last_choch(self) -> StructureEvent | None:
        for ev in reversed(self.events):
            if ev.kind == "CHOCH":
                return ev
        return None


class StructureAnalyzer:
    """
    Bozor tuzilishini tahlil qiladi.

    Ishlatish:
        analyzer = StructureAnalyzer(lookback=2)
        result = analyzer.analyze(df)   # df — get_candles() natijasi
    """

    def __init__(self, lookback: int = 2) -> None:
        # lookback — swing aniqlashda chap/o'ng tomondagi shamlar soni
        self.lookback = lookback

    # ------------------------------------------------------------------ #
    #  1) Swing nuqtalarni topish (fraktal usuli)
    # ------------------------------------------------------------------ #
    def find_swings(self, df: pd.DataFrame) -> tuple[list[SwingPoint], list[SwingPoint]]:
        """Swing High va Swing Low nuqtalarini qaytaradi."""
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        times = df.index
        n = len(df)
        L = self.lookback

        swing_highs: list[SwingPoint] = []
        swing_lows: list[SwingPoint] = []

        for i in range(L, n - L):
            window_h = highs[i - L : i + L + 1]
            window_l = lows[i - L : i + L + 1]

            # Swing High: markaz shami eng baland (ikkala tomondan)
            if highs[i] == window_h.max() and (window_h.argmax() == L):
                swing_highs.append(
                    SwingPoint(index=i, time=times[i], price=float(highs[i]), kind="high")
                )
            # Swing Low: markaz shami eng past
            if lows[i] == window_l.min() and (window_l.argmin() == L):
                swing_lows.append(
                    SwingPoint(index=i, time=times[i], price=float(lows[i]), kind="low")
                )

        return swing_highs, swing_lows

    # ------------------------------------------------------------------ #
    #  2) Trendni aniqlash (oxirgi swinglar bo'yicha)
    # ------------------------------------------------------------------ #
    def determine_trend(
        self, swing_highs: list[SwingPoint], swing_lows: list[SwingPoint]
    ) -> Trend:
        """HH+HL -> BULLISH, LH+LL -> BEARISH, aks holda RANGE."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return Trend.RANGE

        hh = swing_highs[-1].price > swing_highs[-2].price   # Higher High
        hl = swing_lows[-1].price > swing_lows[-2].price     # Higher Low
        lh = swing_highs[-1].price < swing_highs[-2].price   # Lower High
        ll = swing_lows[-1].price < swing_lows[-2].price     # Lower Low

        if hh and hl:
            return Trend.BULLISH
        if lh and ll:
            return Trend.BEARISH
        return Trend.RANGE

    # ------------------------------------------------------------------ #
    #  3) BOS va CHoCH hodisalarini aniqlash
    # ------------------------------------------------------------------ #
    def detect_events(
        self,
        df: pd.DataFrame,
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> list[StructureEvent]:
        """
        Har bir shamda oxirgi tasdiqlangan swing buzilganini tekshiradi.
        - Bullish trendda swing high buzilsa -> BOS (BUY)
        - Bearish trendda swing high buzilsa -> CHoCH (BUY, reversal)
        - va aksincha.
        Faqat body (close) bilan buzilish hisobga olinadi (fake BOS filtri).
        """
        events: list[StructureEvent] = []
        closes = df["close"].to_numpy()
        times = df.index

        # swing nuqtalarni indeks bo'yicha birlashtiramiz
        sh = sorted(swing_highs, key=lambda s: s.index)
        sl = sorted(swing_lows, key=lambda s: s.index)

        current_trend = Trend.RANGE
        hi_ptr, lo_ptr = 0, 0
        last_high: SwingPoint | None = None
        last_low: SwingPoint | None = None
        prev_high: SwingPoint | None = None
        prev_low: SwingPoint | None = None

        for i in range(len(df)):
            # shu shamgacha tasdiqlangan swinglarni yangilaymiz
            while hi_ptr < len(sh) and sh[hi_ptr].index < i:
                prev_high, last_high = last_high, sh[hi_ptr]
                hi_ptr += 1
            while lo_ptr < len(sl) and sl[lo_ptr].index < i:
                prev_low, last_low = last_low, sl[lo_ptr]
                lo_ptr += 1

            # trendni yangilash
            if last_high and prev_high and last_low and prev_low:
                if last_high.price > prev_high.price and last_low.price > prev_low.price:
                    current_trend = Trend.BULLISH
                elif last_high.price < prev_high.price and last_low.price < prev_low.price:
                    current_trend = Trend.BEARISH

            close = closes[i]

            # Yuqoriga buzilish (swing high)
            if last_high and close > last_high.price:
                kind = "BOS" if current_trend == Trend.BULLISH else "CHOCH"
                events.append(
                    StructureEvent(
                        kind=kind,
                        direction=Direction.BUY,
                        price=float(close),
                        time=times[i],
                        broken_swing=last_high.price,
                    )
                )
                # buzilgan swingni "iste'mol qilingan" deb belgilaymiz
                last_high = None

            # Pastga buzilish (swing low)
            if last_low and close < last_low.price:
                kind = "BOS" if current_trend == Trend.BEARISH else "CHOCH"
                events.append(
                    StructureEvent(
                        kind=kind,
                        direction=Direction.SELL,
                        price=float(close),
                        time=times[i],
                        broken_swing=last_low.price,
                    )
                )
                last_low = None

        return events

    # ------------------------------------------------------------------ #
    #  Umumiy tahlil
    # ------------------------------------------------------------------ #
    def analyze(self, df: pd.DataFrame) -> StructureResult:
        swing_highs, swing_lows = self.find_swings(df)
        trend = self.determine_trend(swing_highs, swing_lows)
        events = self.detect_events(df, swing_highs, swing_lows)
        return StructureResult(
            trend=trend,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            events=events,
        )
