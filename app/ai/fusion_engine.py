"""
TITAN AI — Multi-Strategy Fusion Engine (qaror markazi).

Manba: TITAN AI TRADING BIBLE, 40-bob (Institutional Core).
Barcha tahlil modullarini birlashtirib, ovoz berish (voting) + vazn (weight) +
konsensus asosida yagona signal chiqaradi.

Faol ovoz beruvchilar (vazn manbai: constants.ACTIVE_WEIGHTS, jami = 100):
  trend, structure (BOS/CHoCH/MSS), order_block (+Breaker), fvg (+Inverse),
  liquidity, momentum, htf_bias (MTF konfluens), premium_discount (equilibrium).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.core.config import settings
from app.core.constants import (
    ACTIVE_WEIGHTS,
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
from app.strategies import (
    HtfBias,
    MomentumStrategy,
    PremiumDiscountStrategy,
    RegimeDetector,
    VolumeStrategy,
    current_session,
)

# Statik vazn manbai (jami = 100). Regime-adaptiv rejim o'chirilganda ishlatiladi.
WEIGHTS = ACTIVE_WEIGHTS

# Qarama-qarshi ovozlar confidence'ni qancha pasaytiradi (0-1)
CONFLICT_PENALTY: float = 0.4


@dataclass
class ZoneHit:
    """Narxga yaqin yo'nalishli zona (OB/Breaker yoki FVG/Inverse)."""
    direction: Direction
    bottom: float
    top: float
    confidence: float
    label: str

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


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

    def __init__(
        self,
        risk_reward: float = DEFAULT_RR,
        disabled: set[str] | None = None,
        adaptive_weights: bool = False,
        weights_override: dict[str, int] | None = None,
        volume_filter: bool = False,
        min_confidence: float | None = None,
    ) -> None:
        self.risk_reward = risk_reward
        # disabled — o'chirilgan ovozlar (A/B test uchun; ular WAIT ga majburlanadi)
        self.disabled = disabled or set()
        # adaptive_weights — bozor rejimiga qarab vaznlarni moslash (39/14-bob).
        # False bo'lsa statik vaznlar ishlatiladi (eski xatti-harakat, A/B uchun).
        self.adaptive_weights = adaptive_weights
        # weights_override — statik rejimда ACTIVE_WEIGHTS o'rniga maxsus vaznlar
        # (vazn sweep / tuning uchun). adaptive_weights=True bo'lsa e'tiborga olinmaydi.
        self.weights_override = weights_override
        self.structure = StructureAnalyzer(lookback=2)
        self.order_block = OrderBlockAnalyzer()
        self.fvg = FVGAnalyzer()
        self.liquidity = LiquidityAnalyzer()
        self.momentum = MomentumStrategy()
        self.premium_discount = PremiumDiscountStrategy()
        self.htf_bias = HtfBias()
        self.regime_detector = RegimeDetector()
        # volume_filter — Volume Engine (7-bob) bilan fake-breakout signallarni rad etish.
        self.volume_filter = volume_filter
        self.volume = VolumeStrategy()
        # min_confidence — signal chegarasi (Elite selektivlik uchun; None = standart 60).
        self.min_confidence = min_confidence if min_confidence is not None else CONFIDENCE_MIN_SIGNAL

    # ------------------------------------------------------------------ #
    #  Asosiy: DataFrame -> Signal (yoki None, agar WAIT bo'lsa)
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        digits: int = 5,
        now: datetime | None = None,
        htf_df: pd.DataFrame | None = None,
    ) -> FusionResult:
        price = float(df["close"].iloc[-1])
        avg_range = float((df["high"] - df["low"]).mean()) or 1e-9

        # Bozor rejimini aniqlab, mos vazn profilini tanlaymiz (39/14-bob).
        regime = self.regime_detector.detect(df)
        if self.adaptive_weights:
            weights = regime.weights
        else:
            weights = self.weights_override or WEIGHTS

        struct = self.structure.analyze(df)
        votes = self._collect_votes(df, price, avg_range, struct, htf_df, weights)

        buy_score = sum(v.weight for v in votes if v.direction == Direction.BUY)
        sell_score = sum(v.weight for v in votes if v.direction == Direction.SELL)

        direction = Direction.BUY if buy_score > sell_score else (
            Direction.SELL if sell_score > buy_score else Direction.WAIT
        )
        winning, losing = max(buy_score, sell_score), min(buy_score, sell_score)
        # Konflikt jarimasi bilan confidence (0-100)
        confidence = max(0.0, min(100.0, winning - losing * CONFLICT_PENALTY))
        # ICT Kill Zone: savdo sessiyasiga qarab confidence'ni moslash
        session = current_session(now)
        confidence = round(max(0.0, min(100.0, confidence * session.factor)), 1)

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
        if confidence < self.min_confidence:
            result.wait_reason = f"confidence past ({confidence}% < {self.min_confidence}%)"
            return result

        entry, sl, tp = self._calc_levels(direction, price, struct, avg_range, digits)
        if sl is None or tp is None:
            result.wait_reason = "SL/TP hisoblanmadi"
            return result

        # Min SL filtri: juda yaqin SL = sifatsiz signal (shovqin darajasi + ulkan lot xavfi)
        min_sl = settings.min_sl_atr_ratio * avg_range
        if abs(entry - sl) < min_sl:
            result.wait_reason = (
                f"SL juda yaqin ({abs(entry - sl):.5f} < {min_sl:.5f}) — sifatsiz, o'tkazildi"
            )
            log.debug(f"{symbol} {timeframe}: {result.wait_reason}")
            return result

        # Volume tasdiqlash filtri (7-bob): fake-breakout (hajmsiz) signalni rad etadi
        if self.volume_filter:
            ok, vreason = self.volume.confirms(df, direction)
            if not ok:
                result.wait_reason = f"volume: {vreason}"
                log.debug(f"{symbol} {timeframe}: {result.wait_reason}")
                return result

        reasons = [f"{v.strategy}: {v.reason}" for v in votes if v.direction == direction]
        reasons.append(f"session: {session.name} (confidence x{session.factor})")
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
    def _collect_votes(self, df, price, avg_range, struct, htf_df=None,
                       weights=WEIGHTS) -> list[Vote]:
        votes: list[Vote] = []

        # 1) TREND (structure.trend)
        if struct.trend == Trend.BULLISH:
            votes.append(Vote("trend", Direction.BUY, weights["trend"], 80,
                              "trend yuqoriga (HH+HL)"))
        elif struct.trend == Trend.BEARISH:
            votes.append(Vote("trend", Direction.SELL, weights["trend"], 80,
                              "trend pastga (LH+LL)"))
        else:
            votes.append(Vote("trend", Direction.WAIT, weights["trend"], 0,
                              "trend aniq emas (range)"))

        # 2) STRUCTURE EVENT (oxirgi BOS / CHoCH / MSS)
        ev = struct.last_event
        if ev is not None:
            conf = {"MSS": 90, "BOS": 85}.get(ev.kind, 75)
            votes.append(Vote("structure", ev.direction, weights["structure"], conf,
                              f"oxirgi {ev.kind} {ev.direction.value} "
                              f"(swing {ev.broken_swing:.5f} buzildi)"))
        else:
            votes.append(Vote("structure", Direction.WAIT, weights["structure"], 0,
                              "struktura hodisasi yo'q"))

        # 3) ORDER BLOCK / BREAKER (narxga yaqin zona)
        ob = self._ob_zone_hit(df, price, avg_range)
        if ob is not None:
            votes.append(Vote("order_block", ob.direction, weights["order_block"],
                              ob.confidence,
                              f"{ob.direction.value} {ob.label} "
                              f"[{ob.bottom:.5f}-{ob.top:.5f}]"))
        else:
            votes.append(Vote("order_block", Direction.WAIT, weights["order_block"], 0,
                              "yaqin OB/Breaker yo'q"))

        # 4) FVG / INVERSE FVG (narxga yaqin zona)
        fvg = self._fvg_zone_hit(df, price, avg_range)
        if fvg is not None:
            votes.append(Vote("fvg", fvg.direction, weights["fvg"], fvg.confidence,
                              f"{fvg.direction.value} {fvg.label} "
                              f"[{fvg.bottom:.5f}-{fvg.top:.5f}]"))
        else:
            votes.append(Vote("fvg", Direction.WAIT, weights["fvg"], 0,
                              "yaqin FVG yo'q"))

        # 5) LIQUIDITY (oxirgi sweep)
        _, sweeps = self.liquidity.analyze(df)
        if sweeps:
            last_sweep = sweeps[-1]
            votes.append(Vote("liquidity", last_sweep.direction, weights["liquidity"], 75,
                              f"{last_sweep.direction.value} liquidity sweep "
                              f"(daraja {last_sweep.level:.5f})"))
        else:
            votes.append(Vote("liquidity", Direction.WAIT, weights["liquidity"], 0,
                              "sweep yo'q"))

        # 6) MOMENTUM (EMA)
        mom = self.momentum.evaluate(df)
        votes.append(Vote("momentum", mom.direction, weights["momentum"],
                          mom.confidence, mom.reason))

        # 7) HTF BIAS (yuqori taymfrejm konfluensi)
        htf = self.htf_bias.evaluate(htf_df)
        votes.append(Vote("htf_bias", htf.direction, weights["htf_bias"],
                          htf.confidence, htf.reason))

        # 8) PREMIUM / DISCOUNT (equilibrium)
        pd_res = self.premium_discount.evaluate(df)
        votes.append(Vote("premium_discount", pd_res.direction, weights["premium_discount"],
                          pd_res.confidence, pd_res.reason))

        # A/B test: o'chirilgan ovozlarni WAIT ga majburlash (ballarga qo'shilmaydi)
        if self.disabled:
            for v in votes:
                if v.strategy in self.disabled:
                    v.direction = Direction.WAIT
                    v.confidence = 0
                    v.reason = f"[o'chirilgan] {v.reason}"

        return votes

    # ------------------------------------------------------------------ #
    #  Yordamchi: narxga yaqin zona (OB/Breaker, FVG/Inverse)
    # ------------------------------------------------------------------ #
    def _ob_zone_hit(self, df, price, avg_range) -> ZoneHit | None:
        near = 2.0 * avg_range
        hits: list[ZoneHit] = []
        for b in self.order_block.find(df):
            if not b.mitigated and (b.bottom - near) <= price <= (b.top + near):
                hits.append(ZoneHit(b.direction, b.bottom, b.top,
                                    min(95, 60 + b.strength * 10),
                                    f"OB (kuch={b.strength}x)"))
        for br in self.order_block.find_breakers(df):
            if (br.bottom - near) <= price <= (br.top + near):
                hits.append(ZoneHit(br.direction, br.bottom, br.top, 70, "Breaker"))
        if not hits:
            return None
        return min(hits, key=lambda z: abs(z.midpoint - price))

    def _fvg_zone_hit(self, df, price, avg_range) -> ZoneHit | None:
        near = 2.0 * avg_range
        hits: list[ZoneHit] = []
        for g in self.fvg.find(df):
            if not g.filled and (g.bottom - near) <= price <= (g.top + near):
                hits.append(ZoneHit(g.direction, g.bottom, g.top, 70, "FVG"))
        for iv in self.fvg.find_inverse(df):
            if not iv.filled and (iv.bottom - near) <= price <= (iv.top + near):
                hits.append(ZoneHit(iv.direction, iv.bottom, iv.top, 72, "Inverse FVG"))
        if not hits:
            return None
        return min(hits, key=lambda z: abs(z.midpoint - price))

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
