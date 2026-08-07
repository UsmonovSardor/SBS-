"""SignalOutcomeTracker state-machine testi (fake feed/journal/tgbot)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pandas as pd

from app.core.config import settings
from app.tracking import SignalOutcomeTracker


def _bars(rows):
    idx = pd.to_datetime([t for t, *_ in rows])
    data = [{"open": o, "high": h, "low": l, "close": c} for _, o, h, l, c in rows]
    return pd.DataFrame(data, index=idx)


class FakeFeed:
    def __init__(self, df):
        self.df = df

    def get_candles(self, symbol, timeframe, count=300, include_forming=False):
        return self.df


class FakeJournal:
    def __init__(self, rows):
        self.rows = rows
        self.closed = []
        self.updated = []

    def active_tracked(self):
        return [r for r in self.rows if r["status"] == "OPEN"]

    def update_tracked(self, tid, *, stage, eff_sl, last_checked):
        self.updated.append((tid, stage, eff_sl))
        for r in self.rows:
            if r["id"] == tid:
                r["stage"], r["eff_sl"] = stage, eff_sl

    def touch_tracked(self, tid, last_checked):
        pass

    def close_tracked(self, tid, result):
        self.closed.append((tid, result))
        for r in self.rows:
            if r["id"] == tid:
                r["status"] = "CLOSED"


class FakeTgbot:
    def __init__(self):
        self.followups = []

    async def send_followup(self, text, chart_path=None, reply_to=None):
        self.followups.append(text)


class FakeRenderer:
    def render(self, df, signal, zones=None, title=None):
        return None  # grafik yo'q (test)


def _run(feed, journal, tgbot):
    tr = SignalOutcomeTracker(feed, journal, FakeRenderer(), tgbot)
    asyncio.run(tr.check_all())


def _row(**kw):
    base = dict(id=1, symbol="EURUSD", timeframe="M5", direction="BUY", digits=5,
                entry=1.1000, sl=1.0980, tp1=1.1020, tp2=1.1040, tp3=1.1060,
                message_id=10, stage=0, eff_sl=1.0980, status="OPEN",
                last_checked="2024-01-01T00:00:00",
                opened_at=datetime.now().isoformat())  # yaqin -> expiry ishlamaydi
    base.update(kw)
    return base


def test_buy_tp1_then_breakeven():
    # bar1 TP1 ga tegadi (stage->1, eff_sl=entry), bar2 entry (BE) ga qaytib yopiladi
    df = _bars([
        ("2024-01-01 00:00", 1.100, 1.1005, 1.0998, 1.1002),  # last_checked chizig'i (excluded)
        ("2024-01-01 00:05", 1.100, 1.1025, 1.1005, 1.1020),  # TP1 hit
        ("2024-01-01 00:10", 1.102, 1.1010, 1.0995, 1.1000),  # BE (entry) stop
    ])
    journal = FakeJournal([_row()])
    tgbot = FakeTgbot()
    _run(FakeFeed(df), journal, tgbot)
    assert any("TP1" in f for f in tgbot.followups)          # TP1 follow-up ketdi
    assert len(journal.closed) == 1
    assert journal.closed[0][1].startswith("Breakeven")      # zararsiz yopildi


def test_buy_stop_loss_immediate():
    df = _bars([
        ("2024-01-01 00:00", 1.100, 1.1002, 1.0999, 1.1001),
        ("2024-01-01 00:05", 1.100, 1.1005, 1.0979, 1.0980),  # SL hit (stage 0)
    ])
    journal = FakeJournal([_row()])
    tgbot = FakeTgbot()
    _run(FakeFeed(df), journal, tgbot)
    assert len(journal.closed) == 1
    assert journal.closed[0][1].startswith("SL")


def test_expired_open_closed_silently():
    # opened_at juda eski -> jimgina yopiladi, Telegram xabari YO'Q, narx tekshirilmaydi
    old = (datetime.now() - timedelta(hours=settings.outcome_max_age_hours + 1)).isoformat()
    df = _bars([  # narx SL/TP ga tegmaydi — baribir muddat bo'yicha yopilishi kerak
        ("2024-01-01 00:00", 1.100, 1.1001, 1.0999, 1.1000),
        ("2024-01-01 00:05", 1.100, 1.1002, 1.0998, 1.1001),
    ])
    journal = FakeJournal([_row(opened_at=old)])
    tgbot = FakeTgbot()
    _run(FakeFeed(df), journal, tgbot)
    assert len(journal.closed) == 1
    assert "Muddati tugadi" in journal.closed[0][1]
    assert tgbot.followups == []  # jimgina — hech qanday follow-up yuborilmadi


def test_buy_full_tp3():
    df = _bars([
        ("2024-01-01 00:00", 1.100, 1.1001, 1.0999, 1.1000),
        ("2024-01-01 00:05", 1.100, 1.1065, 1.1001, 1.1060),  # bitta shamda TP1->TP2->TP3
    ])
    journal = FakeJournal([_row()])
    tgbot = FakeTgbot()
    _run(FakeFeed(df), journal, tgbot)
    assert len(journal.closed) == 1
    assert journal.closed[0][1].startswith("TP3")
    assert any("TP1" in f for f in tgbot.followups)
    assert any("TP2" in f for f in tgbot.followups)
