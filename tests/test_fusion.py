"""Fusion Engine: vaznlar, analyze va WAIT holati testlari."""
from __future__ import annotations

from app.ai.fusion_engine import FusionEngine, FusionResult, WEIGHTS
from app.core.constants import ACTIVE_WEIGHTS, Direction
from tests._helpers import df_from_closes, make_df, zigzag


def test_weights_sum_to_100():
    assert sum(ACTIVE_WEIGHTS.values()) == 100
    assert WEIGHTS is ACTIVE_WEIGHTS


def test_all_votes_present():
    df = df_from_closes(zigzag([10, 12, 11, 13, 12.5, 15], steps=10))
    engine = FusionEngine()
    res = engine.analyze(df, "TEST", "M15", digits=3)
    strategies = {v.strategy for v in res.votes}
    assert strategies == set(ACTIVE_WEIGHTS.keys())


def test_analyze_returns_result():
    df = df_from_closes(zigzag([10, 12, 11, 13, 12.5, 15], steps=10))
    res = FusionEngine().analyze(df, "TEST", "M15", digits=3)
    assert isinstance(res, FusionResult)
    assert 0 <= res.confidence <= 100


def test_flat_market_waits():
    df = make_df([(10.0, 10.0, 10.0, 10.0)] * 60)
    res = FusionEngine().analyze(df, "TEST", "M15", digits=3)
    assert not res.is_signal
    assert res.direction == Direction.WAIT
