"""Journal: feature-logging (signal_votes) testlari."""
from __future__ import annotations

import importlib

from app.ai.signal import Signal, Vote
from app.core.constants import Direction, SignalStrength


def _make_journal(tmp_path, monkeypatch):
    import app.database.journal as journal_mod
    monkeypatch.setattr(journal_mod, "DB_PATH", tmp_path / "titan.db")
    importlib.reload  # (no-op; DB_PATH modul darajasida ishlatiladi)
    return journal_mod.Journal()


def _signal_with_votes() -> Signal:
    votes = [
        Vote("trend", Direction.BUY, 20, 80, "trend yuqoriga"),
        Vote("structure", Direction.BUY, 18, 85, "BOS BUY"),
        Vote("momentum", Direction.SELL, 12, 55, "EMA past"),
        Vote("liquidity", Direction.WAIT, 10, 0, "sweep yo'q"),
    ]
    return Signal(
        symbol="EURUSD", timeframe="M5", direction=Direction.BUY,
        confidence=72, strength=SignalStrength.MEDIUM,
        entry=1.1000, stop_loss=1.0980, take_profit=1.1040, risk_reward=2.0,
        price_at_signal=1.1000, buy_score=38, sell_score=12,
        tp1=1.1020, tp2=1.1040, tp3=1.1060, votes=votes,
    )


def test_log_features_persists_all_votes(tmp_path, monkeypatch):
    j = _make_journal(tmp_path, monkeypatch)
    sig = _signal_with_votes()
    sig_id = j.log_signal(sig)
    j.log_features(sig_id, sig)

    with j._conn() as c:
        rows = c.execute(
            "SELECT strategy,direction,weight,confidence FROM signal_votes "
            "WHERE signal_id=? ORDER BY id", (sig_id,)
        ).fetchall()
    assert len(rows) == 4
    assert rows[0]["strategy"] == "trend"
    assert rows[0]["direction"] == "BUY"
    assert rows[2]["direction"] == "SELL"      # momentum
    assert rows[3]["confidence"] == 0          # WAIT ovoz


def test_log_features_empty_votes_noop(tmp_path, monkeypatch):
    j = _make_journal(tmp_path, monkeypatch)
    sig = _signal_with_votes()
    sig.votes = []
    sig_id = j.log_signal(sig)
    j.log_features(sig_id, sig)          # xato bermasligi kerak
    with j._conn() as c:
        n = c.execute("SELECT COUNT(*) FROM signal_votes").fetchone()[0]
    assert n == 0
