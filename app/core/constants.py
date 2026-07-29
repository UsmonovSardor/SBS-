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


# --- Fusion engine: FAOL ovoz beruvchilar vazni (jami = 100) ---
# Manba: TITAN AI TRADING BIBLE, 40-bob (Multi-Strategy Fusion).
# MUHIM: bu — Fusion Engine amalda ISHLATADIGAN yagona vazn manbasi.
# Har bir kalit `fusion_engine._collect_votes` dagi bitta ovozga mos keladi.
# (Wyckoff/Elliott/Harmonic/News hali qurilmagan — ular Faza C da qo'shiladi va
#  o'shanda bu jadval qayta muvozanatlanadi.)
ACTIVE_WEIGHTS: dict[str, int] = {
    "trend": 14,            # bozor trendi (HH/HL yoki LH/LL)
    "structure": 15,        # BOS / CHoCH / MSS
    "order_block": 13,      # Order Block + Breaker Block zonalari
    "fvg": 10,              # Fair Value Gap + Inverse FVG
    "liquidity": 14,        # Equal H/L sweep
    "momentum": 9,          # EMA momentum
    "htf_bias": 15,         # yuqori taymfrejm trend konfluensi (MTF)
    "premium_discount": 10,  # equilibrium (faqat discountda BUY, premiumda SELL)
}
assert sum(ACTIVE_WEIGHTS.values()) == 100, "ACTIVE_WEIGHTS jami 100 bo'lishi shart"

# --- Confidence chegaralari ---
CONFIDENCE_MIN_SIGNAL = 60      # bundan past bo'lsa signal berilmaydi
CONFIDENCE_ELITE = 90

# --- Risk ---
DEFAULT_RR = 2.0                # Risk:Reward nisbati (1:2)
MAX_SPREAD_POINTS = 30          # ruxsat etilgan maksimal spread

# --- Grafik ---
CHART_CANDLES = 120             # grafikda ko'rsatiladigan shamlar soni

# --- Execution (MT5) ---
TITAN_MAGIC = 20260728          # TITAN AI ochgan savdolarni tanib olish uchun
DEFAULT_DEVIATION = 20          # narx og'ishi (slippage) ruxsati, punktda
DEFAULT_LOT = 0.01              # zaxira minimal lot
