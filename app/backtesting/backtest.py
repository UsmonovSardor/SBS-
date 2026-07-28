"""
TITAN AI — Backtesting Engine.

Manba: TITAN AI TRADING BIBLE, 13 va 28-boblar.
Tarixiy shamlar bo'yicha oldinga yurib (walk-forward) Fusion Engine signallarini
generatsiya qiladi va virtual savdolarni simulyatsiya qiladi (SL/TP qaysi biri
avval tegishini tekshiradi). Natijada: win-rate, R (risk birligi), profit factor,
maksimal drawdown.

Cheklov: bu soddalashtirilgan model — spread/slippage/komissiya hisobga olinmagan.
Natijalar taxminiy, real savdo bilan aynan mos kelmasligi mumkin.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.ai.fusion_engine import FusionEngine
from app.core.constants import Direction
from app.core.logger import log


@dataclass
class BacktestTrade:
    direction: Direction
    entry: float
    sl: float
    tp: float
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None = None
    exit_price: float = 0.0
    won: bool = False
    r_multiple: float = 0.0


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    trades: list[BacktestTrade] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.won)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if not t.won and t.exit_time is not None)

    @property
    def win_rate(self) -> float:
        closed = self.wins + self.losses
        return round(self.wins / closed * 100, 1) if closed else 0.0

    @property
    def total_r(self) -> float:
        return round(sum(t.r_multiple for t in self.trades), 2)

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.r_multiple for t in self.trades if t.r_multiple > 0)
        gross_loss = abs(sum(t.r_multiple for t in self.trades if t.r_multiple < 0))
        return round(gross_win / gross_loss, 2) if gross_loss else float("inf")

    @property
    def max_drawdown_r(self) -> float:
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.trades:
            equity += t.r_multiple
            peak = max(peak, equity)
            max_dd = min(max_dd, equity - peak)
        return round(max_dd, 2)


class Backtester:
    """Walk-forward backtest."""

    def __init__(self, engine: FusionEngine | None = None,
                 window: int = 160, warmup: int = 160) -> None:
        self.engine = engine or FusionEngine()
        self.window = window
        self.warmup = warmup

    def run(self, df: pd.DataFrame, symbol: str, timeframe: str,
            digits: int = 5) -> BacktestResult:
        result = BacktestResult(symbol=symbol, timeframe=timeframe)
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        times = df.index
        n = len(df)

        open_trade: BacktestTrade | None = None
        i = self.warmup

        while i < n:
            # Ochiq savdo bor bo'lsa — shu shamda SL/TP tegdimi
            if open_trade is not None:
                closed = self._check_exit(open_trade, highs[i], lows[i], times[i])
                if closed:
                    result.trades.append(open_trade)
                    open_trade = None
                i += 1
                continue

            # Yangi signal qidiramiz (yopilgan shamlar bo'yicha)
            window_df = df.iloc[max(0, i - self.window): i + 1]
            res = self.engine.analyze(window_df, symbol, timeframe, digits=digits,
                                      now=times[i].to_pydatetime())
            if res.is_signal:
                s = res.signal
                open_trade = BacktestTrade(
                    direction=s.direction, entry=s.entry, sl=s.stop_loss,
                    tp=s.take_profit, entry_time=times[i],
                )
            i += 1

        return result

    def _check_exit(self, trade: BacktestTrade, high: float, low: float,
                    t: pd.Timestamp) -> bool:
        """SL yoki TP tegdimi. Ikkalasi bir shamda bo'lsa — SL birinchi (ehtiyotkor)."""
        sl_dist = abs(trade.entry - trade.sl)
        tp_dist = abs(trade.tp - trade.entry)
        rr = tp_dist / sl_dist if sl_dist else 0

        if trade.direction == Direction.BUY:
            if low <= trade.sl:
                trade.exit_time, trade.exit_price, trade.won, trade.r_multiple = t, trade.sl, False, -1.0
                return True
            if high >= trade.tp:
                trade.exit_time, trade.exit_price, trade.won, trade.r_multiple = t, trade.tp, True, rr
                return True
        else:  # SELL
            if high >= trade.sl:
                trade.exit_time, trade.exit_price, trade.won, trade.r_multiple = t, trade.sl, False, -1.0
                return True
            if low <= trade.tp:
                trade.exit_time, trade.exit_price, trade.won, trade.r_multiple = t, trade.tp, True, rr
                return True
        return False
