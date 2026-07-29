"""Order Block va Breaker Block testlari."""
from __future__ import annotations

from app.core.constants import Direction
from app.smc.order_block import OrderBlockAnalyzer
from tests._helpers import make_df


def _base_bars():
    # kichik shamlar + bitta bearish + kuchli bullish displacement -> Bullish OB
    return [
        (10.0, 10.06, 9.94, 10.0),
        (10.0, 10.06, 9.94, 10.0),
        (10.0, 10.05, 9.85, 9.9),    # idx2: bearish (kelajakdagi OB)
        (9.9, 11.05, 9.85, 11.0),    # idx3: kuchli bullish displacement
        (11.0, 11.06, 10.94, 11.0),
    ]


def test_bullish_order_block():
    df = make_df(_base_bars())
    blocks = OrderBlockAnalyzer().find(df)
    assert any(b.direction == Direction.BUY for b in blocks)


def test_breaker_block_flips_direction():
    bars = _base_bars()
    # OB zonasini (bottom=9.85) close bilan pastga buzamiz -> SELL breaker
    bars.append((11.0, 11.05, 9.4, 9.5))   # idx5: bottom'dan past yopiladi
    df = make_df(bars)
    breakers = OrderBlockAnalyzer().find_breakers(df)
    assert any(br.direction == Direction.SELL for br in breakers), (
        f"SELL breaker kutilgan: {[(b.direction, b.bottom, b.top) for b in breakers]}"
    )
