"""
TITAN AI — Signal obyekti (Signal Object).

Manba: TITAN AI TRADING BIBLE, 11.12-bob.
Fusion Engine yakuniy qaror sifatida shu obyektni qaytaradi. U keyin:
  - Grok tomonidan tushuntiriladi,
  - grafikka chiziladi,
  - Telegram'ga yuboriladi,
  - Auto-Trade tugmasi orqali MT5'da bajariladi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.core.constants import Direction, SignalStrength


@dataclass
class Vote:
    """Bitta strategiyaning ovozi."""
    strategy: str          # masalan "trend", "order_block"
    direction: Direction   # BUY | SELL | WAIT
    weight: float          # strategiya vazni
    confidence: float      # 0-100 (shu strategiyaning ishonchi)
    reason: str            # inson o'qiy oladigan izoh (o'zbekcha)


@dataclass
class Signal:
    """Yakuniy savdo signali."""
    symbol: str
    timeframe: str
    direction: Direction              # BUY | SELL
    confidence: float                 # 0-100
    strength: SignalStrength

    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float

    price_at_signal: float
    buy_score: float
    sell_score: float

    votes: list[Vote] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    ai_explanation: str = ""          # Grok tushuntirishi (keyin to'ldiriladi)
    created_at: datetime = field(default_factory=datetime.now)

    # ------------------------------------------------------------------ #
    @property
    def is_buy(self) -> bool:
        return self.direction == Direction.BUY

    @property
    def sl_distance(self) -> float:
        """Entry va Stop Loss orasidagi masofa (narxda)."""
        return abs(self.entry - self.stop_loss)

    @property
    def tp_distance(self) -> float:
        return abs(self.take_profit - self.entry)

    def summary(self) -> str:
        """Qisqa matnli xulosa (loglar uchun)."""
        arrow = "🟢 BUY" if self.is_buy else "🔴 SELL"
        return (
            f"{arrow}  {self.symbol} ({self.timeframe})  "
            f"conf={self.confidence:.0f}% [{self.strength.value}]  "
            f"entry={self.entry}  SL={self.stop_loss}  TP={self.take_profit}  "
            f"RR=1:{self.risk_reward:.1f}"
        )
