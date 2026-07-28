"""
TITAN AI — Bozor ma'lumotlari (Market Data Feed).

MT5 dan shamlar (OHLC), joriy narx (tick) va simvol ma'lumotlarini oladi.
Shamlar pandas DataFrame ko'rinishida qaytariladi — tahlil modullari shu bilan ishlaydi.
"""
from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5
import pandas as pd

from app.core.constants import Timeframe
from app.core.exceptions import MarketDataError
from app.core.logger import log

# Bizning Timeframe enum -> MT5 konstantalari
TIMEFRAME_MAP: dict[Timeframe, int] = {
    Timeframe.M1: mt5.TIMEFRAME_M1,
    Timeframe.M5: mt5.TIMEFRAME_M5,
    Timeframe.M15: mt5.TIMEFRAME_M15,
    Timeframe.M30: mt5.TIMEFRAME_M30,
    Timeframe.H1: mt5.TIMEFRAME_H1,
    Timeframe.H4: mt5.TIMEFRAME_H4,
    Timeframe.D1: mt5.TIMEFRAME_D1,
    Timeframe.W1: mt5.TIMEFRAME_W1,
}


@dataclass
class SymbolInfo:
    """Simvol texnik ma'lumotlari."""
    name: str
    digits: int          # narxdan keyingi kasr xonalar soni
    point: float         # eng kichik narx qadami
    spread: int          # joriy spread (punktlarda)
    trade_allowed: bool
    volume_min: float
    volume_max: float
    volume_step: float


@dataclass
class Tick:
    """Joriy narx (bir lahzalik)."""
    symbol: str
    bid: float
    ask: float
    spread: float        # ask - bid (narxda)
    time: pd.Timestamp


class DataFeed:
    """Bozor ma'lumotlarini olishga mas'ul modul (MT5 ulangan bo'lishi shart)."""

    # ------------------------------------------------------------------ #
    #  Simvolni tayyorlash
    # ------------------------------------------------------------------ #
    @staticmethod
    def ensure_symbol(symbol: str) -> None:
        """Simvolni Market Watch'ga qo'shadi (aks holda ma'lumot kelmaydi)."""
        info = mt5.symbol_info(symbol)
        if info is None:
            raise MarketDataError(f"Simvol topilmadi: {symbol}")
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                raise MarketDataError(f"Simvolni tanlab bo'lmadi: {symbol}")

    # ------------------------------------------------------------------ #
    #  Simvol ma'lumoti
    # ------------------------------------------------------------------ #
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        self.ensure_symbol(symbol)
        raw = mt5.symbol_info(symbol)
        if raw is None:
            raise MarketDataError(f"symbol_info olinmadi: {symbol}")
        return SymbolInfo(
            name=raw.name,
            digits=raw.digits,
            point=raw.point,
            spread=raw.spread,
            trade_allowed=raw.trade_mode != 0,
            volume_min=raw.volume_min,
            volume_max=raw.volume_max,
            volume_step=raw.volume_step,
        )

    # ------------------------------------------------------------------ #
    #  Joriy narx (tick)
    # ------------------------------------------------------------------ #
    def get_tick(self, symbol: str) -> Tick:
        self.ensure_symbol(symbol)
        t = mt5.symbol_info_tick(symbol)
        if t is None:
            raise MarketDataError(f"Tick olinmadi: {symbol}")
        return Tick(
            symbol=symbol,
            bid=t.bid,
            ask=t.ask,
            spread=round(t.ask - t.bid, 8),
            time=pd.to_datetime(t.time, unit="s"),
        )

    # ------------------------------------------------------------------ #
    #  Shamlar (candles / OHLC)
    # ------------------------------------------------------------------ #
    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe = Timeframe.M15,
        count: int = 300,
    ) -> pd.DataFrame:
        """
        Oxirgi `count` ta shamni DataFrame ko'rinishida qaytaradi.

        Ustunlar: time (index), open, high, low, close, tick_volume, spread, real_volume
        """
        self.ensure_symbol(symbol)
        mt5_tf = TIMEFRAME_MAP[timeframe]

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None or len(rates) == 0:
            code, desc = mt5.last_error()
            raise MarketDataError(
                f"Shamlar olinmadi: {symbol} {timeframe.value} — [{code}] {desc}"
            )

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        log.debug(f"{symbol} {timeframe.value}: {len(df)} ta sham olindi")
        return df
