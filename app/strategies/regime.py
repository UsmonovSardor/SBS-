"""
TITAN AI — Market Regime Detector + Strategy Selector.

Manba: TITAN AI TRADING BIBLE, 39-bob (Market Regime) + 14-bob (Strategy Selector).

Institutsional mantiq: bozor har doim bir xil emas. Ba'zan kuchli TREND, ba'zan
RANGE (yon harakat). Strategiyalar bir vaqtda emas — REJIMGA qarab prioritet
oladi:
  • TREND rejimida: trend / structure / momentum ustun ("trend bilan").
  • RANGE rejimida: liquidity / premium_discount / order_block / fvg ustun
    (reversal — sweep'dan qaytish, equilibrium'dan qaytish).

Rejim "Efficiency Ratio" (Kaufman) bilan aniqlanadi — tashqi kutubxonasiz, ishonchli:
    ER = |close[-1] - close[-n]| / Σ|close.diff()|   (n = lookback)
ER → 1 : yo'nalishli (trend);  ER → 0 : shovqinli (range).

Bu modul fusion'ga har rejim uchun VAZN PROFILINI beradi (har biri jami = 100).
Vaznlar prinsipial (trend rejimi → trend ovozlari), muayyan namunaga moslab
"optimallashtirilmagan" — overfit'dan qochish uchun.

⚠️ HOLAT (2026-08-05): `FusionEngine(adaptive_weights=...)` DEFAULT = False, ya'ni
bu tizim JONLI botда HALI FAOL EMAS. Sabab: H4 (3 simvol, 2 yil) namunasida
adaptiv statik vazndan yaxshi chiqmadi — namuna kichik, natija mo'rt. Ko'proq
validatsiya ma'lumoti (ko'proq simvol/tarix + walk-forward) bilan profillar qayta
baholanib, tasdiqlangач yoqiladi. Infratuzilma tayyor, ovozlar mexanizmi ishlaydi.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from app.core.constants import ACTIVE_WEIGHTS


class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"


# Efficiency Ratio chegarasi: bundan yuqori = trend, past = range.
ER_TREND_THRESHOLD = 0.35
ER_LOOKBACK = 24  # nechta shamda yo'nalishlilikni o'lchash (H4'da ~4 kun)


# --- Har rejim uchun vazn profili (jami = 100) ---
# Kalitlar constants.ACTIVE_WEIGHTS bilan bir xil (8 ovoz).
_TRENDING_WEIGHTS: dict[str, int] = {
    "trend": 20,             # trend ovozlari ustun
    "structure": 19,
    "momentum": 14,
    "order_block": 14,
    "fvg": 9,
    "liquidity": 13,
    "premium_discount": 11,
}
_RANGING_WEIGHTS: dict[str, int] = {
    "liquidity": 20,         # range'da sweep/reversal ustun
    "premium_discount": 17,  # equilibrium'dan qaytish
    "order_block": 17,
    "fvg": 13,
    "structure": 15,
    "trend": 9,              # range'da trend ovozi zaif
    "momentum": 9,
}

WEIGHT_PROFILES: dict[MarketRegime, dict[str, int]] = {
    MarketRegime.TRENDING: _TRENDING_WEIGHTS,
    MarketRegime.RANGING: _RANGING_WEIGHTS,
}

# Profil kalitlari ACTIVE_WEIGHTS bilan mos va jami 100 ekanini kafolatlash
for _rg, _w in WEIGHT_PROFILES.items():
    assert set(_w) == set(ACTIVE_WEIGHTS), f"{_rg}: vazn kalitlari ACTIVE_WEIGHTS bilan mos emas"
    assert sum(_w.values()) == 100, f"{_rg}: vaznlar jami 100 bo'lishi shart"


@dataclass
class RegimeResult:
    regime: MarketRegime
    efficiency_ratio: float
    reason: str

    @property
    def weights(self) -> dict[str, int]:
        return WEIGHT_PROFILES[self.regime]


class RegimeDetector:
    """Efficiency Ratio asosida bozor rejimini aniqlaydi."""

    def __init__(self, lookback: int = ER_LOOKBACK,
                 threshold: float = ER_TREND_THRESHOLD) -> None:
        self.lookback = lookback
        self.threshold = threshold

    def detect(self, df: pd.DataFrame) -> RegimeResult:
        close = df["close"]
        n = min(self.lookback, len(close) - 1)
        if n < 5:
            # Ma'lumot yetarli emas — ehtiyotkorlik uchun RANGE (reversal profil)
            return RegimeResult(MarketRegime.RANGING, 0.0, "ma'lumot kam (default range)")

        net = abs(float(close.iloc[-1]) - float(close.iloc[-1 - n]))
        path = float(close.diff().abs().iloc[-n:].sum()) or 1e-9
        er = net / path

        if er >= self.threshold:
            return RegimeResult(MarketRegime.TRENDING, round(er, 3),
                                f"trend (ER={er:.2f} ≥ {self.threshold})")
        return RegimeResult(MarketRegime.RANGING, round(er, 3),
                            f"range (ER={er:.2f} < {self.threshold})")
