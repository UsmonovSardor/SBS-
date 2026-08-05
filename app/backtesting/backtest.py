"""
TITAN AI — Backtesting Engine (xarajatli, real-ga yaqin).

Manba: TITAN AI TRADING BIBLE, 13 va 28-boblar.
Tarixiy shamlar bo'yicha oldinga yurib (walk-forward) Fusion Engine signallarini
generatsiya qiladi va virtual savdolarni simulyatsiya qiladi (SL/TP qaysi biri
avval tegishini tekshiradi).

Faza B yaxshilanishlari:
  - SPREAD + KOMISSIYA modeli (har savdo R natijasidan chegiriladi) — real edge
    faqat xarajatdan keyin qoladi.
  - Boy metrikalar: expectancy, Sharpe (savdo bo'yicha), o'rtacha win/loss R,
    ketma-ket maksimal zarar, profit factor, maksimal drawdown.
  - Out-of-sample uchun `run` istalgan df bo'lagida ishlaydi (train/test bo'lish
    chaqiruvchi tomonda qilinadi).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import pstdev

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
    gross_r: float = 0.0     # xarajatsiz R (win=+rr, loss=-1)
    cost_r: float = 0.0      # spread+komissiya (R ulushida)
    r_multiple: float = 0.0  # sof R (gross - cost)


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    trades: list[BacktestTrade] = field(default_factory=list)

    # ---- asosiy ----
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
        """Sof jami R (xarajatdan keyin)."""
        return round(sum(t.r_multiple for t in self.trades), 2)

    @property
    def gross_r(self) -> float:
        """Xarajatsiz jami R (taqqoslash uchun)."""
        return round(sum(t.gross_r for t in self.trades), 2)

    @property
    def cost_r(self) -> float:
        """Umumiy xarajat (R da) — spread/komissiya qancha yedi."""
        return round(sum(t.cost_r for t in self.trades), 2)

    # ---- sifat metrikalari ----
    @property
    def expectancy(self) -> float:
        """Har savdoga o'rtacha sof R (edge o'lchovi). >0 = ijobiy edge."""
        return round(self.total_r / self.total, 3) if self.total else 0.0

    @property
    def avg_win_r(self) -> float:
        w = [t.r_multiple for t in self.trades if t.won]
        return round(sum(w) / len(w), 2) if w else 0.0

    @property
    def avg_loss_r(self) -> float:
        loss = [t.r_multiple for t in self.trades if not t.won and t.exit_time is not None]
        return round(sum(loss) / len(loss), 2) if loss else 0.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.r_multiple for t in self.trades if t.r_multiple > 0)
        gross_loss = abs(sum(t.r_multiple for t in self.trades if t.r_multiple < 0))
        return round(gross_win / gross_loss, 2) if gross_loss else float("inf")

    @property
    def sharpe(self) -> float:
        """Savdo bo'yicha Sharpe (o'rtacha R / standart og'ish) — barqarorlik o'lchovi."""
        rs = [t.r_multiple for t in self.trades]
        if len(rs) < 2:
            return 0.0
        sd = pstdev(rs)
        return round((sum(rs) / len(rs)) / sd, 2) if sd else 0.0

    @property
    def max_consecutive_losses(self) -> int:
        streak = mx = 0
        for t in self.trades:
            if not t.won and t.exit_time is not None:
                streak += 1
                mx = max(mx, streak)
            else:
                streak = 0
        return mx

    @property
    def max_drawdown_r(self) -> float:
        equity = peak = max_dd = 0.0
        for t in self.trades:
            equity += t.r_multiple
            peak = max(peak, equity)
            max_dd = min(max_dd, equity - peak)
        return round(max_dd, 2)

    def summary(self) -> dict[str, float | int]:
        return {
            "trades": self.total,
            "win_rate": self.win_rate,
            "expectancy": self.expectancy,
            "total_r": self.total_r,
            "gross_r": self.gross_r,
            "cost_r": self.cost_r,
            "profit_factor": self.profit_factor,
            "sharpe": self.sharpe,
            "max_dd_r": self.max_drawdown_r,
            "max_consec_loss": self.max_consecutive_losses,
        }


class Backtester:
    """Xarajatli walk-forward backtest."""

    def __init__(
        self,
        engine: FusionEngine | None = None,
        window: int = 160,
        warmup: int = 160,
        spread: float = 0.0,
        commission: float = 0.0,
    ) -> None:
        self.engine = engine or FusionEngine()
        self.window = window
        self.warmup = warmup
        # spread, commission — NARX birligida (round-trip umumiy xarajat = spread+commission)
        self.spread = spread
        self.commission = commission

    def run(self, df: pd.DataFrame, symbol: str, timeframe: str,
            digits: int = 5, htf_df: pd.DataFrame | None = None) -> BacktestResult:
        """
        htf_df — yuqori taymfrejm (masalan H4 uchun D1) shamlari. Berilса, har
        barда FAQAT o'sha lahzagacha YOPILGAN HTF shamlar uzatiladi (jonli
        bot `include_forming=False` bilan bir xil — repaint yo'q). Shu tariqa
        htf_bias ovozi ham backtestда jonli konfiguratsiyadagidek sinaladi.
        """
        result = BacktestResult(symbol=symbol, timeframe=timeframe)
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        times = df.index
        n = len(df)

        # HTF sham davomiyligi (bir sham qachon "yopiladi" ni bilish uchun)
        htf_freq = None
        if htf_df is not None and len(htf_df) > 1:
            htf_freq = htf_df.index.to_series().diff().dropna().median()

        open_trade: BacktestTrade | None = None
        i = self.warmup

        while i < n:
            if open_trade is not None:
                if self._check_exit(open_trade, highs[i], lows[i], times[i]):
                    result.trades.append(open_trade)
                    open_trade = None
                i += 1
                continue

            window_df = df.iloc[max(0, i - self.window): i + 1]
            # Faqat shu bardan oldin to'liq yopilgan HTF shamlar (repaint yo'q)
            htf_window = None
            if htf_freq is not None:
                closed = htf_df[htf_df.index + htf_freq <= times[i]]
                htf_window = closed if len(closed) >= 10 else None
            res = self.engine.analyze(window_df, symbol, timeframe, digits=digits,
                                      now=times[i].to_pydatetime(), htf_df=htf_window)
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
        """
        SL yoki TP tegdimi. Ikkalasi bir shamda bo'lsa — SL birinchi (ehtiyotkor).
        Xarajat (spread+komissiya) har natijadan chegiriladi.
        """
        sl_dist = abs(trade.entry - trade.sl)
        tp_dist = abs(trade.tp - trade.entry)
        rr = tp_dist / sl_dist if sl_dist else 0.0
        cost_r = (self.spread + self.commission) / sl_dist if sl_dist else 0.0

        def close(won: bool, price: float) -> None:
            trade.exit_time = t
            trade.exit_price = price
            trade.won = won
            trade.cost_r = round(cost_r, 4)
            trade.gross_r = rr if won else -1.0
            trade.r_multiple = round(trade.gross_r - cost_r, 4)

        if trade.direction == Direction.BUY:
            if low <= trade.sl:
                close(False, trade.sl)
                return True
            if high >= trade.tp:
                close(True, trade.tp)
                return True
        else:  # SELL
            if high >= trade.sl:
                close(False, trade.sl)
                return True
            if low <= trade.tp:
                close(True, trade.tp)
                return True
        return False
