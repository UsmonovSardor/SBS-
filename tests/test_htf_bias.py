"""Higher-Timeframe bias (MTF konfluens) testlari."""
from __future__ import annotations

from app.core.constants import Direction
from app.strategies import HtfBias, higher_timeframe
from app.core.constants import Timeframe
from tests._helpers import df_from_closes, zigzag


def test_none_htf_waits():
    assert HtfBias().evaluate(None).direction == Direction.WAIT


def test_bullish_htf_gives_buy():
    df = df_from_closes(zigzag([10, 12, 11, 13, 12.5, 15]))
    assert HtfBias().evaluate(df).direction == Direction.BUY


def test_bearish_htf_gives_sell():
    df = df_from_closes(zigzag([15, 13, 14, 12, 13, 10]))
    assert HtfBias().evaluate(df).direction == Direction.SELL


def test_htf_map_returns_higher():
    assert higher_timeframe(Timeframe.M5) == Timeframe.H1
    assert higher_timeframe(Timeframe.M15) == Timeframe.H4
