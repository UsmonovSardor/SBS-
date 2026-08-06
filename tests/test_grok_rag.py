"""Grok build_prompt — RAG (bilim bazasi) konteksti qo'shilishi testi."""
from __future__ import annotations

from app.ai.grok_client import GrokClient
from app.ai.signal import Signal, Vote
from app.core.constants import Direction, SignalStrength


def _sig() -> Signal:
    return Signal(
        symbol="EURUSD", timeframe="M5", direction=Direction.BUY,
        confidence=72, strength=SignalStrength.MEDIUM,
        entry=1.1, stop_loss=1.098, take_profit=1.104, risk_reward=2.0,
        price_at_signal=1.1, buy_score=38, sell_score=12,
        votes=[Vote("order_block", Direction.BUY, 15, 70, "BUY OB zona")],
    )


def test_prompt_without_kb_has_no_kb_block():
    p = GrokClient().build_prompt(_sig())
    assert "BILIM BAZASIDAN" not in p
    assert "EURUSD" in p


def test_prompt_with_kb_includes_context():
    p = GrokClient().build_prompt(_sig(), kb_context="[Order Block] OB institutsional zona.")
    assert "BILIM BAZASIDAN" in p
    assert "institutsional zona" in p
