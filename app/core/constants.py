"""
TITAN AI — Umumiy konstantalar va enumlar.
"Magic number" ishlatmaslik uchun barcha turg'un qiymatlar shu yerda.
"""
from __future__ import annotations

from enum import Enum


class Direction(str, Enum):
    """Savdo yo'nalishi."""
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"          # signal yo'q / kutish


class Trend(str, Enum):
    """Bozor trendi."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"


class Timeframe(str, Enum):
    """MT5 taймфреймлари (string ko'rinishida)."""
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


class SignalStrength(str, Enum):
    """Signal kuchi (confidence darajasi bo'yicha)."""
    WEAK = "WEAK"           # < 60
    MEDIUM = "MEDIUM"       # 60-79
    STRONG = "STRONG"       # 80-89
    ELITE = "ELITE"         # >= 90


# --- Fusion engine: strategiya vaznlari (jami = 100) ---
# Manba: TITAN AI TRADING BIBLE, 40-bob (Multi-Strategy Fusion)
STRATEGY_WEIGHTS: dict[str, int] = {
    "trend": 20,
    "liquidity": 20,
    "smc": 15,
    "ict": 10,
    "wyckoff": 10,
    "elliott": 10,
    "harmonic": 5,
    "news": 10,
}

# --- Confidence chegaralari ---
CONFIDENCE_MIN_SIGNAL = 60      # bundan past bo'lsa signal berilmaydi
CONFIDENCE_ELITE = 90

# --- Risk ---
DEFAULT_RR = 2.0                # Risk:Reward nisbati (1:2)
MAX_SPREAD_POINTS = 30          # ruxsat etilgan maksimal spread

# --- Grafik ---
CHART_CANDLES = 120             # grafikda ko'rsatiladigan shamlar soni
