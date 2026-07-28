"""
TITAN AI — Multi-Strategy Fusion Engine (qaror markazi).

Manba: TITAN AI TRADING BIBLE, 40-bob (Institutional Core).
Barcha tahlil modullarini (Structure, Order Block, FVG, Liquidity) birlashtirib,
ovoz berish (voting) + vazn (weight) + konsensus asosida yagona signal chiqaradi.

MVP bosqichi: 5 ta ovoz beruvchi (trend, struktura, order block, fvg, liquidity).
Keyin ICT / Wyckoff / Harmonic / News qo'shiladi (vaznlar qayta taqsimlanadi).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.constants import (
    CONFIDENCE_ELITE,
    CONFIDENCE_MIN_SIGNAL,
    DEFAULT_RR,
    Direction,
    SignalStrength,
    Trend,
)
from app.core.logger import log
from app.ai.signal import Signal, Vote
from app.smc import (
    FVGAnalyzer,
    LiquidityAnalyzer,
    OrderBlockAnalyzer,
    StructureAnalyzer,
)

# MVP ovoz beruvchilar vazni (jami = 100)
MVP_WEIGHTS: dict[str, float] = {
    "trend": 25,
    "structure": 20,   # BOS / CHoCH
    "order_block": 20,
    "fvg": 15,
    "liquidity": 20,
}

# Qarama-qarshi ovozlar confidence'ni qancha pasaytiradi (0-1)
CONFLICT_PENALTY: float = 0.4


@dataclass
class FusionResult:
    """Fusion tahlilining to'liq natijasi (signal bo'lsa ham, WAIT bo'lsa ham)."""
    symbol: str
    timeframe: str
    direction: Direction
    confidence: float
    buy_score: float
    sell_score: float
    votes: list[Vote] = field(default_factory=list)
    signal: Signal | None = None      # None => WAIT (savdo ochilmaydi)
    wait_reason: str = ""

    @property
    def is_signal(self) -> bool:
        return self.signal is not None


class FusionEngine:
    """Strategiyalarni birlashtirib yakuniy signal chiqaradi."""

    def __init__(self, risk_reward: float = DEFAULT_RR) -> None:
        self.risk_reward = risk_reward
        self.structure = StructureAnalyzer(lookback=2)
        self.order_block = OrderBlockAnalyzer()
        self.fvg = FVGAnalyzer()
        self.liquidity = LiquidityAnalyzer()

    # ------------------------------------------------------------------ #
    #  Asosiy: DataFrame -> Signal (yoki None, agar WAIT bo'lsa)
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        digits: int = 5,
    ) -> FusionResult:
        price = float(df["close"].iloc[-1])
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9

        struct = self.structure.analyze(df)
        votes = self._collect_votes(df, price, avg_range, struct)

        buy_score = sum(v.weight for v in votes if v.direction == Direction.BUY)
        sell_score = sum(v.weight for v in votes if v.direction == Direction.SELL)

        direction = Direction.BUY if buy_score > sell_score else (
            Direction.SELL if sell_score > buy_score else Direction.WAIT
        )
        winning, losing = max(buy_score, sell_score), min(buy_score, sell_score)
        # Konflikt jarimasi bilan confidence (0-100)
        confidence = round(max(0.0, min(100.0, winning - losing * CONFLICT_PENALTY)), 1)

        result = FusionResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            buy_score=buy_score,
            sell_score=sell_score,
            votes=votes,
        )

        # WAIT shartlari
        if direction == Direction.WAIT:
            result.wait_reason = "buy va sell ballari teng"
            return result
        if confidence < CONFIDENCE_MIN_SIGNAL:
            result.wait_reason = f"confidence past ({confidence}% < {CONFIDENCE_MIN_SIGNAL}%)"
            return result

        entry, sl, tp = self._calc_levels(direction, price, struct, avg_range, digits)
        if sl is None or tp is None:
            result.wait_reason = "SL/TP hisoblanmadi"
            return result

        reasons = [f"{v.strategy}: {v.reason}" for v in votes if v.direction == direction]
        result.signal = Signal(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            strength=self._strength(confidence),
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            risk_reward=self.risk_reward,
            price_at_signal=round(price, digits),
            buy_score=buy_score,
            sell_score=sell_score,
            votes=votes,
            reasons=reasons,
        )
        log.info(result.signal.summary())
        return result

    # ------------------------------------------------------------------ #
    #  Ovozlarni yig'ish
    # ------------------------------------------------------------------ #
    def _collect_votes(self, df, price, avg_range, struct) -> list[Vote]:
        votes: list[Vote] = []

        # 1) TREND (structure.trend)
        if struct.trend == Trend.BULLISH:
            votes.append(Vote("trend", Direction.BUY, MVP_WEIGHTS["trend"], 80,
                              "trend yuqoriga (HH+HL)"))
        elif struct.trend == Trend.BEARISH:
            votes.append(Vote("trend", Direction.SELL, MVP_WEIGHTS["trend"], 80,
                              "trend pastga (LH+LL)"))
        else:
            votes.append(Vote("trend", Direction.WAIT, MVP_WEIGHTS["trend"], 0,
                              "trend aniq emas (range)"))

        # 2) STRUCTURE EVENT (oxirgi BOS/CHoCH)
        ev = struct.last_event
        if ev is not None:
            conf = 85 if ev.kind == "BOS" else 75
            votes.append(Vote("structure", ev.direction, MVP_WEIGHTS["structure"], conf,
                              f"oxirgi {ev.kind} {ev.direction.value} "
                              f"(swing {ev.broken_swing:.5f} buzildi)"))
        else:
            votes.append(Vote("structure", Direction.WAIT, MVP_WEIGHTS["structure"], 0,
                              "struktura hodisasi yo'q"))

        # 3) ORDER BLOCK (narxga yaqin fresh OB)
        ob = self._nearest_fresh_ob(df, price, avg_range)
        if ob is not None:
            votes.append(Vote("order_block", ob.direction, MVP_WEIGHTS["order_block"],
                              min(95, 60 + ob.strength * 10),
                              f"{ob.direction.value} OB zona [{ob.bottom:.5f}-{ob.top:.5f}] "
                              f"kuch={ob.strength}x"))
        else:
            votes.append(Vote("order_block", Direction.WAIT, MVP_WEIGHTS["order_block"], 0,
                              "yaqin fresh OB yo'q"))

        # 4) FVG (narxga yaqin fresh FVG)
        fvg = self._nearest_fresh_fvg(df, price, avg_range)
        if fvg is not None:
            votes.append(Vote("fvg", fvg.direction, MVP_WEIGHTS["fvg"], 70,
                              f"{fvg.direction.value} FVG bo'shliq "
                              f"[{fvg.bottom:.5f}-{fvg.top:.5f}]"))
        else:
            votes.append(Vote("fvg", Direction.WAIT, MVP_WEIGHTS["fvg"], 0,
                              "yaqin fresh FVG yo'q"))

        # 5) LIQUIDITY (oxirgi sweep)
        _, sweeps = self.liquidity.analyze(df)
        if sweeps:
            last_sweep = sweeps[-1]
            votes.append(Vote("liquidity", last_sweep.direction, MVP_WEIGHTS["liquidity"], 75,
                              f"{last_sweep.direction.value} liquidity sweep "
                              f"(daraja {last_sweep.level:.5f})"))
        else:
            votes.append(Vote("liquidity", Direction.WAIT, MVP_WEIGHTS["liquidity"], 0,
                              "sweep yo'q"))

        return votes

    # ------------------------------------------------------------------ #
    #  Yordamchi: narxga yaqin fresh OB / FVG
    # ------------------------------------------------------------------ #
    def _nearest_fresh_ob(self, df, price, avg_range):
        near = 2.0 * avg_range
        candidates = [
            b for b in self.order_block.find(df)
            if not b.mitigated and (b.bottom - near) <= price <= (b.top + near)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda b: abs(b.midpoint - price))

    def _nearest_fresh_fvg(self, df, price, avg_range):
        near = 2.0 * avg_range
        candidates = [
            g for g in self.fvg.find(df)
            if not g.filled and (g.bottom - near) <= price <= (g.top + near)
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda g: abs(g.midpoint - price))

    # ------------------------------------------------------------------ #
    #  Entry / Stop Loss / Take Profit
    # ------------------------------------------------------------------ #
    def _calc_levels(self, direction, price, struct, avg_range, digits):
        buffer = 0.3 * avg_range
        entry = round(price, digits)

        if direction == Direction.BUY:
            lows = [s.price for s in struct.swing_lows if s.price < price]
            sl_raw = (max(lows) if lows else price - 1.5 * avg_range) - buffer
            sl = round(sl_raw, digits)
            tp = round(entry + self.risk_reward * (entry - sl), digits)
        else:  # SELL
            highs = [s.price for s in struct.swing_highs if s.price > price]
            sl_raw = (min(highs) if highs else price + 1.5 * avg_range) + buffer
            sl = round(sl_raw, digits)
            tp = round(entry - self.risk_reward * (sl - entry), digits)

        # SL entry bilan bir xil bo'lib qolsa — signal bekor
        if sl == entry:
            return entry, None, None
        return entry, sl, tp

    # ------------------------------------------------------------------ #
    @staticmethod
    def _strength(confidence: float) -> SignalStrength:
        if confidence >= CONFIDENCE_ELITE:
            return SignalStrength.ELITE
        if confidence >= 80:
            return SignalStrength.STRONG
        if confidence >= CONFIDENCE_MIN_SIGNAL:
            return SignalStrength.MEDIUM
        return SignalStrength.WEAK
