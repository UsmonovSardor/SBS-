"""
TITAN AI — MT5 Execution Engine (savdo ochish/yopish).

Manba: TITAN AI TRADING BIBLE, 12-bob.
Signal asosida MT5 demo/real account'da market order ochadi (SL/TP bilan),
ochiq pozitsiyalarni ko'radi va yopadi.

XAVFSIZLIK: trading_mode='demo' bo'lganda faqat demo account'da ishlaydi.
Live rejim uchun alohida tasdiq talab qilinadi (open_signal(confirm_live=True)).
"""
from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5

from app.core.config import settings
from app.core.constants import (
    DEFAULT_DEVIATION,
    DEFAULT_LOT,
    Direction,
    TITAN_MAGIC,
)
from app.core.exceptions import ExecutionError
from app.core.logger import log
from app.ai.signal import Signal
from app.market.data_feed import DataFeed
from app.market.mt5_connector import MT5Connector
from app.risk.position_sizer import PositionSizer


@dataclass
class TradeResult:
    """Savdo bajarilishi natijasi."""
    success: bool
    retcode: int
    message: str
    order: int = 0          # ochilgan order/pozitsiya ticket
    price: float = 0.0      # bajarilgan narx
    volume: float = 0.0     # lot
    lot_info: str = ""      # lot hisobi izohi


@dataclass
class Position:
    """Ochiq pozitsiya (soddalashtirilgan)."""
    ticket: int
    symbol: str
    direction: Direction
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    magic: int


class TradeExecutor:
    """MT5 savdo bajaruvchi."""

    def __init__(
        self,
        connector: MT5Connector | None = None,
        feed: DataFeed | None = None,
    ) -> None:
        self.conn = connector or MT5Connector()
        self.feed = feed or DataFeed()
        self.sizer = PositionSizer()

    # ------------------------------------------------------------------ #
    #  Signal asosida savdo ochish
    # ------------------------------------------------------------------ #
    def open_signal(
        self,
        signal: Signal,
        lot: float | None = None,
        risk_percent: float | None = None,
        confirm_live: bool = False,
    ) -> TradeResult:
        """
        Signal bo'yicha market order ochadi.
        - lot berilsa — o'sha lot; aks holda risk asosida hisoblanadi.
        - Live rejimda confirm_live=True bo'lishi shart (xavfsizlik).
        """
        self.conn.ensure_connected()

        # Xavfsizlik: live rejim himoyasi
        acc = self.conn.account_info()
        if not acc.is_demo and not confirm_live:
            raise ExecutionError(
                "REAL account! Savdo ochilmadi. Live savdo uchun confirm_live=True kerak."
            )

        info = self.feed.get_symbol_info(signal.symbol)
        if not info.trade_allowed:
            raise ExecutionError(f"{signal.symbol}: savdo taqiqlangan")

        tick = self.feed.get_tick(signal.symbol)
        is_buy = signal.is_buy
        price = tick.ask if is_buy else tick.bid

        # --- Lot hisoblash ---
        lot_info = ""
        if lot is None:
            rp = risk_percent if risk_percent is not None else settings.default_risk_percent
            calc = self.sizer.calculate(acc.balance, rp, signal.entry, signal.stop_loss, info)
            lot = calc.lot
            lot_info = (f"risk {rp}% = {calc.risk_amount} {acc.currency}, "
                        f"loss/lot={calc.loss_per_lot}, lot={lot}"
                        + (" (clamped)" if calc.clamped else ""))

        # --- SL/TP ni minimal masofaga moslash ---
        sl, tp = self._adjust_stops(signal, price, info, is_buy)

        # --- So'rov (request) ---
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": signal.symbol,
            "volume": float(lot),
            "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": DEFAULT_DEVIATION,
            "magic": TITAN_MAGIC,
            "comment": "TITAN AI",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }

        log.info(f"Savdo ochilmoqda: {signal.symbol} {'BUY' if is_buy else 'SELL'} "
                 f"lot={lot} price={price} SL={sl} TP={tp}")
        result = mt5.order_send(request)

        if result is None:
            code, desc = mt5.last_error()
            raise ExecutionError(f"order_send None qaytardi: [{code}] {desc}")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"Savdo rad etildi: retcode={result.retcode} — {result.comment}")
            return TradeResult(
                success=False, retcode=result.retcode,
                message=result.comment, volume=lot, lot_info=lot_info,
            )

        log.info(f"✅ Savdo ochildi: ticket={result.order} price={result.price} lot={result.volume}")
        return TradeResult(
            success=True, retcode=result.retcode, message="ochildi",
            order=result.order, price=result.price, volume=result.volume, lot_info=lot_info,
        )

    # ------------------------------------------------------------------ #
    #  Ochiq pozitsiyalar
    # ------------------------------------------------------------------ #
    def positions(self, symbol: str | None = None) -> list[Position]:
        self.conn.ensure_connected()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if raw is None:
            return []
        out: list[Position] = []
        for p in raw:
            out.append(Position(
                ticket=p.ticket,
                symbol=p.symbol,
                direction=Direction.BUY if p.type == mt5.POSITION_TYPE_BUY else Direction.SELL,
                volume=p.volume,
                price_open=p.price_open,
                sl=p.sl,
                tp=p.tp,
                profit=p.profit,
                magic=p.magic,
            ))
        return out

    # ------------------------------------------------------------------ #
    #  Pozitsiyani yopish
    # ------------------------------------------------------------------ #
    def close_position(self, ticket: int) -> TradeResult:
        self.conn.ensure_connected()
        raw = mt5.positions_get(ticket=ticket)
        if not raw:
            raise ExecutionError(f"Pozitsiya topilmadi: ticket={ticket}")
        p = raw[0]
        info = self.feed.get_symbol_info(p.symbol)
        tick = self.feed.get_tick(p.symbol)

        if p.type == mt5.POSITION_TYPE_BUY:
            order_type, price = mt5.ORDER_TYPE_SELL, tick.bid
        else:
            order_type, price = mt5.ORDER_TYPE_BUY, tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": DEFAULT_DEVIATION,
            "magic": TITAN_MAGIC,
            "comment": "TITAN AI close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            code = result.retcode if result else -1
            msg = result.comment if result else "None"
            log.error(f"Yopish rad etildi: retcode={code} — {msg}")
            return TradeResult(success=False, retcode=code, message=msg)

        log.info(f"✅ Pozitsiya yopildi: ticket={ticket} profit={p.profit}")
        return TradeResult(success=True, retcode=result.retcode, message="yopildi",
                           order=ticket, price=result.price, volume=p.volume)

    # ------------------------------------------------------------------ #
    #  Yordamchilar
    # ------------------------------------------------------------------ #
    def _adjust_stops(self, signal: Signal, price: float, info, is_buy: bool):
        """SL/TP ni broker minimal masofasiga (stops_level) moslaydi."""
        sl, tp = signal.stop_loss, signal.take_profit
        min_dist = info.stops_level * info.point
        if min_dist <= 0:
            return sl, tp

        if is_buy:
            if price - sl < min_dist:
                sl = round(price - min_dist, info.digits)
            if tp - price < min_dist:
                tp = round(price + min_dist, info.digits)
        else:
            if sl - price < min_dist:
                sl = round(price + min_dist, info.digits)
            if price - tp < min_dist:
                tp = round(price - min_dist, info.digits)
        return sl, tp

    @staticmethod
    def _filling_mode(info) -> int:
        """Simvol ruxsat etgan filling rejimini tanlaydi (IOC > FOK > RETURN)."""
        mode = info.filling_mode
        if mode & 2:   # SYMBOL_FILLING_IOC
            return mt5.ORDER_FILLING_IOC
        if mode & 1:   # SYMBOL_FILLING_FOK
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN
