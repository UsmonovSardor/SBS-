"""Market Structure: swing, trend, BOS/CHoCH va MSS testlari."""
from __future__ import annotations

from app.core.constants import Trend
from app.smc.structure import StructureAnalyzer
from tests._helpers import df_from_closes, make_df, zigzag


def test_swings_detected():
    df = df_from_closes(zigzag([10, 12, 11, 13, 12, 14]))
    sa = StructureAnalyzer()
    highs, lows = sa.find_swings(df)
    assert len(highs) >= 1
    assert len(lows) >= 1


def test_bullish_trend():
    # ko'tariluvchi zigzag: HH + HL
    df = df_from_closes(zigzag([10, 12, 11, 13, 12.5, 15]))
    res = StructureAnalyzer().analyze(df)
    assert res.trend == Trend.BULLISH


def test_bearish_trend():
    # tushuvchi zigzag: LH + LL
    df = df_from_closes(zigzag([15, 13, 14, 12, 13, 10]))
    res = StructureAnalyzer().analyze(df)
    assert res.trend == Trend.BEARISH


def test_mss_on_strong_choch():
    # Uptrend (HH+HL), keyin bitta kuchli (displacement) sham swing low'ni buzadi -> MSS
    closes = zigzag([10, 12, 11, 13], steps=4)
    bars = df_from_closes(closes).values.tolist()  # (o,h,l,c)
    # kuchli tushuvchi displacement sham: oxirgi swing low (11) dan pastga
    o = closes[-1]
    bars.append((o, o + 0.05, 8.9, 9.0))  # katta tanali bearish sham
    df = make_df(bars)
    res = StructureAnalyzer(mss_displacement_ratio=1.5).analyze(df)
    kinds = [e.kind for e in res.events]
    assert "MSS" in kinds, f"MSS kutilgan edi, topilgan: {kinds}"
    assert res.last_mss is not None
    assert res.last_mss.displacement >= 1.5
