"""Backtest: xarajat modeli va sifat metrikalari testlari."""
from __future__ import annotations

import pandas as pd

from app.backtesting.backtest import Backtester, BacktestResult, BacktestTrade
from app.core.constants import Direction

T0 = pd.Timestamp("2024-01-01")


def _trade(entry=1.0, sl=0.99, tp=1.02, direction=Direction.BUY):
    return BacktestTrade(direction=direction, entry=entry, sl=sl, tp=tp, entry_time=T0)


def test_win_applies_cost():
    # sl_dist=0.01, rr=2, cost_r = 0.001/0.01 = 0.1  -> net = 2 - 0.1 = 1.9
    bt = Backtester(spread=0.001)
    tr = _trade()
    assert bt._check_exit(tr, high=1.02, low=1.0, t=T0) is True
    assert tr.won is True
    assert tr.gross_r == 2.0
    assert tr.cost_r == 0.1
    assert tr.r_multiple == 1.9


def test_loss_applies_cost():
    bt = Backtester(spread=0.001)
    tr = _trade()
    assert bt._check_exit(tr, high=1.001, low=0.99, t=T0) is True
    assert tr.won is False
    assert tr.r_multiple == -1.1   # -1 - 0.1


def test_sl_first_on_same_bar():
    # Bir shamda SL ham, TP ham tegsa -> SL birinchi (ehtiyotkor, zarar)
    bt = Backtester(spread=0.0)
    tr = _trade()
    assert bt._check_exit(tr, high=1.02, low=0.99, t=T0) is True
    assert tr.won is False


def test_zero_spread_equals_gross():
    bt = Backtester(spread=0.0, commission=0.0)
    tr = _trade()
    bt._check_exit(tr, high=1.02, low=1.0, t=T0)
    assert tr.r_multiple == tr.gross_r == 2.0


def _closed(r_multiple: float, won: bool) -> BacktestTrade:
    t = _trade()
    t.exit_time = T0
    t.won = won
    t.r_multiple = r_multiple
    return t


def test_result_metrics():
    res = BacktestResult(symbol="X", timeframe="M15")
    res.trades = [
        _closed(1.9, True),
        _closed(-1.1, False),
        _closed(-1.1, False),
        _closed(1.9, True),
    ]
    assert res.total == 4
    assert res.wins == 2
    assert res.losses == 2
    assert res.win_rate == 50.0
    assert res.total_r == 1.6
    assert res.expectancy == 0.4
    assert res.profit_factor == 1.73
    assert res.max_consecutive_losses == 2
    assert res.max_drawdown_r == -2.2
    assert res.sharpe == 0.27
