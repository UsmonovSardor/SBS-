"""Market Regime Detector testlari (sintetik ma'lumot, MT5 kerak emas)."""
from __future__ import annotations

from app.strategies.regime import MarketRegime, RegimeDetector, WEIGHT_PROFILES
from app.core.constants import ACTIVE_WEIGHTS
from tests._helpers import df_from_closes


def test_trending_series_is_trending():
    # Barqaror ko'tariluvchi narx -> Efficiency Ratio yuqori -> TRENDING
    closes = [1.0 + i * 0.01 for i in range(40)]
    res = RegimeDetector().detect(df_from_closes(closes))
    assert res.regime == MarketRegime.TRENDING
    assert res.efficiency_ratio >= 0.35


def test_choppy_series_is_ranging():
    # Bir diapazonda tebranish -> ER past -> RANGING
    closes = [1.0 + (0.01 if i % 2 == 0 else -0.01) for i in range(40)]
    res = RegimeDetector().detect(df_from_closes(closes))
    assert res.regime == MarketRegime.RANGING
    assert res.efficiency_ratio < 0.35


def test_profiles_valid():
    # Har rejim profili ACTIVE_WEIGHTS kalitlariga mos va jami 100
    for regime, w in WEIGHT_PROFILES.items():
        assert set(w) == set(ACTIVE_WEIGHTS)
        assert sum(w.values()) == 100


def test_weights_property_returns_profile():
    res = RegimeDetector().detect(df_from_closes([1.0 + i * 0.01 for i in range(40)]))
    assert res.weights is WEIGHT_PROFILES[res.regime]
