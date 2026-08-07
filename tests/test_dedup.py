"""SignalTracker (dedup) testi — bir setup takror signal bermasligini tekshiradi."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from app.core.constants import Direction, SignalStrength
from app.ai.signal import Signal
from app.orchestrator import SignalTracker


def _sig(symbol="EURUSD", direction=Direction.BUY, tf="M5") -> Signal:
    return Signal(
        symbol=symbol, timeframe=tf, direction=direction, confidence=80,
        strength=SignalStrength.STRONG, entry=1.1000, stop_loss=1.0980,
        take_profit=1.1040, tp1=1.1020, tp2=1.1040, tp3=1.1060, risk_reward=2.0,
        price_at_signal=1.1000, buy_score=0, sell_score=0, created_at=datetime.now(),
    )


def test_open_key_blocks_duplicate():
    # Shu simvol+yo'nalish allaqachon OCHIQ bo'lsa — yangi signal bermaydi
    tr = SignalTracker(cooldown_min=15)
    t = pd.Timestamp("2024-01-01 00:00")
    open_keys = {("EURUSD", "BUY")}
    assert tr.is_new(_sig(), t, open_keys) is False


def test_open_key_allows_other_symbol_or_direction():
    tr = SignalTracker(cooldown_min=15)
    t = pd.Timestamp("2024-01-01 00:00")
    open_keys = {("EURUSD", "BUY")}
    # boshqa yo'nalish (SELL) va boshqa simvol bloklanmaydi
    assert tr.is_new(_sig(direction=Direction.SELL), t, open_keys) is True
    assert tr.is_new(_sig(symbol="USDCHF"), t, open_keys) is True


def test_cooldown_still_applies_without_open_keys():
    tr = SignalTracker(cooldown_min=15)
    t1 = pd.Timestamp("2024-01-01 00:00")
    s = _sig()
    assert tr.is_new(s, t1) is True
    tr.mark(s, t1)
    # cooldown ichida yangi shamda ham qayta bermaydi
    t2 = pd.Timestamp("2024-01-01 00:05")
    assert tr.is_new(_sig(), t2) is False


def test_backward_compatible_no_open_keys_arg():
    # open_keys berilmasa ham ishlaydi (default bo'sh) — eski chaqiruvlar buzilmaydi
    tr = SignalTracker(cooldown_min=15)
    assert tr.is_new(_sig(), pd.Timestamp("2024-01-01 00:00")) is True
