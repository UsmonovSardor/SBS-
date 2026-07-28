"""
TITAN AI — Real-time Orchestrator (bosh boshqaruvchi).

Uzluksiz ishlaydigan bot:
  1) Har SCAN_INTERVAL soniyada barcha simvol × taymfrejmlarni skanlaydi
  2) Fusion Engine signal topsa — takrorlanmaganini tekshiradi (dedup + cooldown)
  3) Grafik chizadi + Grok tahlili oladi
  4) Telegram guruhga yuboradi (Auto-Trade tugmasi bilan)
  5) Bir vaqtning o'zida Telegram polling ishlaydi (tugmalar jonli)

Ikki vazifa parallel: scanner_loop() va Telegram polling (asyncio.gather).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pandas as pd

from app import __version__
from app.ai import FusionEngine, GrokClient
from app.ai.signal import Signal
from app.charting import ChartRenderer, Zone
from app.core.config import settings
from app.core.constants import Timeframe
from app.core.logger import log
from app.execution import PositionMonitor, TradeExecutor
from app.market import DataFeed, MT5Connector
from app.smc import FVGAnalyzer, OrderBlockAnalyzer
from app.telegram import TitanTelegramBot


class SignalTracker:
    """Signallarni takrorlashdan saqlaydi (dedup + cooldown)."""

    def __init__(self, cooldown_min: int) -> None:
        self.cooldown = timedelta(minutes=cooldown_min)
        self._last_by_symbol: dict[str, datetime] = {}
        self._last_key: dict[tuple, pd.Timestamp] = {}

    def is_new(self, signal: Signal, candle_time: pd.Timestamp) -> bool:
        # Bir simvol bo'yicha cooldown
        last = self._last_by_symbol.get(signal.symbol)
        if last and datetime.now() - last < self.cooldown:
            return False
        # Aynan shu shamdagi shu yo'nalish qayta yuborilmaydi
        key = (signal.symbol, signal.timeframe, signal.direction)
        if self._last_key.get(key) == candle_time:
            return False
        return True

    def mark(self, signal: Signal, candle_time: pd.Timestamp) -> None:
        self._last_by_symbol[signal.symbol] = datetime.now()
        self._last_key[(signal.symbol, signal.timeframe, signal.direction)] = candle_time


class TitanOrchestrator:
    """TITAN AI bosh boshqaruvchisi."""

    def __init__(self) -> None:
        self.conn = MT5Connector()
        self.feed = DataFeed()
        self.executor = TradeExecutor(self.conn, self.feed)
        self.engine = FusionEngine()
        self.grok = GrokClient()
        self.renderer = ChartRenderer()
        self.tgbot = TitanTelegramBot(executor=self.executor)
        self.tracker = SignalTracker(settings.signal_cooldown_min)
        self.monitor = PositionMonitor(self.executor)
        self.ob = OrderBlockAnalyzer()
        self.fvg = FVGAnalyzer()

        self.symbols = settings.symbols
        self.timeframes = [Timeframe(t) for t in settings.scan_timeframe_list]
        self.running = True

    # ------------------------------------------------------------------ #
    #  Skanlash (sinxron — bir tsikl)
    # ------------------------------------------------------------------ #
    def _scan_sync(self) -> list[tuple[Signal, pd.DataFrame]]:
        """Barcha simvol×TF ni skanlab, YANGI signallarni qaytaradi."""
        new_signals: list[tuple[Signal, pd.DataFrame]] = []
        for symbol in self.symbols:
            for tf in self.timeframes:
                try:
                    info = self.feed.get_symbol_info(symbol)
                    df = self.feed.get_candles(symbol, tf, count=200)
                    res = self.engine.analyze(df, symbol, tf.value, digits=info.digits)
                    if res.is_signal:
                        candle_time = df.index[-1]
                        if self.tracker.is_new(res.signal, candle_time):
                            self.tracker.mark(res.signal, candle_time)
                            new_signals.append((res.signal, df))
                except Exception as e:  # noqa: BLE001
                    log.debug(f"{symbol} {tf.value}: {e}")
        return new_signals

    def _build_zones(self, df: pd.DataFrame, price: float) -> list[Zone]:
        avg_range = float((df["high"] - df["low"]).mean())
        near = 3 * avg_range
        zones: list[Zone] = []
        for b in self.ob.find(df):
            if not b.mitigated and (b.bottom - near) <= price <= (b.top + near):
                zones.append(Zone(b.bottom, b.top, "#f7b731", f"OB {b.direction.value}"))
        for g in self.fvg.find(df):
            if not g.filled and (g.bottom - near) <= price <= (g.top + near):
                zones.append(Zone(g.bottom, g.top, "#a55eea", f"FVG {g.direction.value}"))
        return zones[:4]

    # ------------------------------------------------------------------ #
    #  Skaner tsikli (async)
    # ------------------------------------------------------------------ #
    async def scanner_loop(self) -> None:
        while self.running:
            try:
                new_signals = self._scan_sync()
                for signal, df in new_signals:
                    chart = self.renderer.render(df, signal, zones=self._build_zones(df, signal.price_at_signal))
                    # Grok tarmoq chaqiruvi — event loop'ni bloklamaslik uchun thread'da
                    signal.ai_explanation = await asyncio.to_thread(self.grok.explain_signal, signal)
                    await self.tgbot.send_signal(signal, chart)
                    log.info(f"📤 Yangi signal yuborildi: {signal.summary()}")

                    # AUTO_TRADE yoqilgan bo'lsa — tugmasiz avtomatik savdo
                    if settings.auto_trade:
                        result = await asyncio.to_thread(self.executor.open_signal, signal)
                        log.info(f"🤖 Avto-savdo: {'ochildi #' + str(result.order) if result.success else result.message}")
            except Exception as e:  # noqa: BLE001
                log.error(f"Skaner tsikli xatoligi: {e}")
            await asyncio.sleep(settings.scan_interval)

    # ------------------------------------------------------------------ #
    #  Pozitsiya monitoring tsikli (break-even + trailing)
    # ------------------------------------------------------------------ #
    async def monitor_loop(self) -> None:
        if not settings.position_manage:
            log.info("Pozitsiya monitoringi o'chirilgan (POSITION_MANAGE=false).")
            return
        while self.running:
            try:
                await asyncio.to_thread(self.monitor.manage_all)
            except Exception as e:  # noqa: BLE001
                log.error(f"Monitor tsikli xatoligi: {e}")
            await asyncio.sleep(settings.monitor_interval)

    # ------------------------------------------------------------------ #
    #  Ishga tushirish
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        self.conn.connect()
        acc = self.conn.account_info()
        log.info("=" * 58)
        log.info(f"  🦅 TITAN AI v{__version__} — REAL-TIME rejim ishga tushdi")
        log.info(f"  Account: {acc.login} [{'DEMO' if acc.is_demo else 'REAL'}]  "
                 f"balans={acc.balance} {acc.currency}")
        log.info(f"  Simvollar: {', '.join(self.symbols)}")
        log.info(f"  Taymfrejmlar: {', '.join(t.value for t in self.timeframes)}")
        log.info(f"  Skan oralig'i: {settings.scan_interval}s  |  "
                 f"cooldown: {settings.signal_cooldown_min} daq")
        log.info(f"  Auto-trade (tugmasiz): {settings.auto_trade}")
        log.info(f"  Telegram guruh: {settings.telegram_channel_id}")
        log.info("=" * 58)

        # Telegram polling + skaner + monitoring parallel
        await asyncio.gather(
            self.tgbot.dp.start_polling(self.tgbot.bot),
            self.scanner_loop(),
            self.monitor_loop(),
        )

    async def close(self) -> None:
        self.running = False
        await self.tgbot.close()
        self.conn.disconnect()
