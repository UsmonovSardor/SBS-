"""
TITAN AI — Position Sizing (lot hajmini hisoblash).

Manba: TITAN AI TRADING BIBLE, 5.3 va 26-bob.
"Capital First" — har savdoda kapitalning belgilangan % dan ortiq risk qilinmaydi.

Formula:
    risk_amount  = balance * risk% / 100          (necha pul risk qilamiz)
    loss_per_lot = (SL masofasi / tick_size) * tick_value
    lot          = risk_amount / loss_per_lot
    -> volume_step ga yaxlitlanadi, [volume_min, volume_max] oralig'iga qisiladi
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.config import settings
from app.core.logger import log
from app.market.data_feed import SymbolInfo


@dataclass
class LotResult:
    """Lot hisoblash natijasi (shaffoflik uchun barcha oraliq qiymatlar bilan)."""
    lot: float
    risk_amount: float          # tavakkal qilingan pul
    loss_per_lot: float         # 1 lotда SL'gacha zarar
    sl_distance: float          # entry-SL masofasi (narxda)
    clamped: bool = False       # min/max/cap ga qisildimi
    capped: bool = False        # xavfsizlik cheklovi (max_lot) ishladimi
    raw_lot: float = 0.0        # cheklovsiz hisoblangan lot (ogohlantirish uchun)


class PositionSizer:
    """Risk foiziga qarab lot hajmini hisoblaydi."""

    def calculate(
        self,
        balance: float,
        risk_percent: float,
        entry: float,
        stop_loss: float,
        info: SymbolInfo,
        max_lot: float | None = None,
    ) -> LotResult:
        sl_distance = abs(entry - stop_loss)
        if sl_distance <= 0:
            raise ValueError("SL masofasi 0 — lot hisoblab bo'lmaydi")

        tick_size = info.tick_size or info.point
        tick_value = info.tick_value or 1.0

        risk_amount = balance * risk_percent / 100.0
        loss_per_lot = (sl_distance / tick_size) * tick_value
        raw_lot = risk_amount / loss_per_lot if loss_per_lot > 0 else info.volume_min

        # volume_step ga pastga yaxlitlash
        step = info.volume_step or 0.01
        lot = math.floor(raw_lot / step) * step
        lot = round(lot, 8)

        # min/max chegara (broker)
        clamped = False
        if lot < info.volume_min:
            lot = info.volume_min
            clamped = True
        elif lot > info.volume_max:
            lot = info.volume_max
            clamped = True

        # XAVFSIZLIK cheklovi: TITAN max_lot (juda yaqin SL -> ulkan lot muammosi)
        cap = max_lot if max_lot is not None else settings.max_lot
        capped = False
        if cap > 0 and lot > cap:
            log.warning(
                f"⚠️ Lot {lot} xavfsizlik chegarasidan ({cap}) oshdi — {cap} ga cheklandi. "
                f"(SL juda yaqin: {sl_distance}). Riskingiz {risk_percent}% dan KAM bo'ladi."
            )
            lot = round(cap, 8)
            capped = True

        log.debug(
            f"Lot hisob: balance={balance} risk={risk_percent}% "
            f"risk_amount={risk_amount:.2f} loss/lot={loss_per_lot:.2f} "
            f"raw={raw_lot:.2f} -> lot={lot}"
            f"{' (clamped)' if clamped else ''}{' (CAPPED)' if capped else ''}"
        )
        return LotResult(
            lot=lot,
            risk_amount=round(risk_amount, 2),
            loss_per_lot=round(loss_per_lot, 2),
            sl_distance=sl_distance,
            clamped=clamped,
            capped=capped,
            raw_lot=round(raw_lot, 2),
        )
