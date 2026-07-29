"""Fair Value Gap va Inverse FVG testlari."""
from __future__ import annotations

from app.core.constants import Direction
from app.smc.fvg import FVGAnalyzer
from tests._helpers import make_df


def test_bullish_fvg_detected():
    # idx0 high < idx2 low -> bullish FVG [10.1, 10.25]
    bars = [
        (10.0, 10.1, 9.9, 10.0),     # c1: high 10.1
        (10.0, 10.2, 9.95, 10.1),    # c2 (o'rta)
        (10.3, 10.5, 10.25, 10.4),   # c3: low 10.25
        (10.4, 10.55, 10.35, 10.45),  # zonaga tegmaydi (fresh)
    ]
    df = make_df(bars)
    gaps = FVGAnalyzer().find(df)
    assert any(g.direction == Direction.BUY for g in gaps)


def test_inverse_fvg_flips_direction():
    bars = [
        (10.0, 10.1, 9.9, 10.0),
        (10.0, 10.2, 9.95, 10.1),
        (10.3, 10.5, 10.25, 10.4),   # bullish FVG [10.1, 10.25]
        (10.4, 10.45, 9.8, 9.85),    # close 9.85 < bottom 10.1 -> inverse
    ]
    df = make_df(bars)
    inv = FVGAnalyzer().find_inverse(df)
    assert any(g.direction == Direction.SELL and g.inverted for g in inv), (
        f"SELL inverse FVG kutilgan: {[(g.direction, g.inverted) for g in inv]}"
    )
