"""Premium / Discount (equilibrium) strategiyasi testlari."""
from __future__ import annotations

from app.core.constants import Direction
from app.strategies import PremiumDiscountStrategy
from tests._helpers import make_df

# Umumiy range: high=110, low=100 (equilibrium=105)
_FRAME = [
    (105, 110, 104, 106),
    (106, 108, 103, 104),
    (104, 106, 100, 101),   # low 100
    (101, 105, 101, 103),
]


def _df_last(close: float):
    return make_df(_FRAME + [(close, close + 0.5, close - 0.5, close)])


def test_discount_gives_buy():
    res = PremiumDiscountStrategy().evaluate(_df_last(102))  # pos ~0.2
    assert res.direction == Direction.BUY
    assert res.confidence > 0


def test_premium_gives_sell():
    res = PremiumDiscountStrategy().evaluate(_df_last(108))  # pos ~0.8
    assert res.direction == Direction.SELL


def test_equilibrium_waits():
    res = PremiumDiscountStrategy().evaluate(_df_last(105))  # pos ~0.5
    assert res.direction == Direction.WAIT
