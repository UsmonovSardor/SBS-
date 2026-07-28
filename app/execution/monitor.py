"""
TITAN AI — Position Monitor (ochiq savdolarni boshqarish).

Manba: TITAN AI TRADING BIBLE, 25.16 (Break Even) va 25.17 (Trailing Stop).
Har bir TITAN pozitsiyasi uchun:
  - Break-Even: narx TP tomon yetarli yursa, SL ni entry'ga ko'chiradi (zararsizlik)
  - Trailing:   narx davom etsa, SL ni orqadan ergashtiradi (foydani qulflaydi)
SL faqat FOYDALI tomonga (buyда yuqoriga, sellда pastga) ko'chiriladi.
"""
from __future__ import annotations

from app.core.config import settings
from app.core.constants import TITAN_MAGIC, Direction
from app.core.logger import log
from app.execution.executor import Position, TradeExecutor


class PositionMonitor:
    """Ochiq TITAN pozitsiyalarini boshqaradi (BE + trailing)."""

    def __init__(self, executor: TradeExecutor) -> None:
        self.executor = executor
        self.feed = executor.feed

    def manage_all(self) -> list[str]:
        """Barcha TITAN pozitsiyalarini tekshiradi. Bajarilgan amallar ro'yxatini qaytaradi."""
        actions: list[str] = []
        for p in self.executor.positions():
            if p.magic != TITAN_MAGIC:
                continue
            try:
                msg = self._manage_one(p)
                if msg:
                    actions.append(msg)
                    log.info(f"🛡️ {msg}")
            except Exception as e:  # noqa: BLE001
                log.debug(f"Monitor #{p.ticket}: {e}")
        return actions

    def _manage_one(self, p: Position) -> str | None:
        if p.tp == 0:
            return None  # TP yo'q — boshqarib bo'lmaydi

        info = self.feed.get_symbol_info(p.symbol)
        tick = self.feed.get_tick(p.symbol)
        is_buy = p.direction == Direction.BUY
        entry = p.price_open
        price = tick.bid if is_buy else tick.ask

        # TP tomon qancha yurdi (0..1)
        if is_buy:
            total = p.tp - entry
            progress = (price - entry) / total if total > 0 else 0
        else:
            total = entry - p.tp
            progress = (entry - price) / total if total > 0 else 0

        if progress <= 0:
            return None  # hali foydada emas

        desired_sl: float | None = None
        reason = ""

        # 1) Break-even
        if progress >= settings.break_even_progress:
            desired_sl = entry
            reason = "break-even"

        # 2) Trailing (BE'dan kuchliroq bo'lsa)
        if progress >= settings.trail_start_progress:
            if is_buy:
                trail = entry + (price - entry) * settings.trail_lock
                if desired_sl is None or trail > desired_sl:
                    desired_sl, reason = trail, "trailing"
            else:
                trail = entry - (entry - price) * settings.trail_lock
                if desired_sl is None or trail < desired_sl:
                    desired_sl, reason = trail, "trailing"

        if desired_sl is None:
            return None

        desired_sl = round(desired_sl, info.digits)
        min_step = info.point * 2
        cur = p.sl

        # Faqat foydali va sezilarli o'zgarish bo'lsa
        if is_buy and cur and desired_sl <= cur + min_step:
            return None
        if (not is_buy) and cur and desired_sl >= cur - min_step:
            return None

        res = self.executor.modify_sltp(p.ticket, sl=desired_sl)
        if res.success:
            return (f"#{p.ticket} {p.symbol}: SL → {desired_sl} "
                    f"({reason}, TP tomon {progress * 100:.0f}%)")
        return None
