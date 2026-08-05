"""
TITAN AI — Signal natijasini kuzatuvchi (Signal Outcome Tracker).

Manba: TITAN AI TRADING BIBLE, 5.9 (Partial Close) + 9.16 (Trade Monitoring).

Har yuborilgan signalni narx harakati bilan solishtiradi va TP1/TP2/TP3 yoki
himoya stopi tegganда asl signalga JAVOB (thread) qilib, grafik bilan aniq
follow-up yuboradi. SL tegsa bitim TO'LIQ yopiladi. Holat SQLite'da saqlanadi
(bot qayta ishga tushса ham kuzatuv davom etadi).

Professional trailing-stop mantiqi (chalkashmaslik uchun bitta aniq bosqichli oqim):
  stage 0 (ochiq):   himoya stop = asl SL
  stage 1 (TP1 olindi): himoya stop = Entry (zararsiz / breakeven)
  stage 2 (TP2 olindi): himoya stop = TP1 (+1R qulflandi)
  TP3 yoki himoya stop teksa -> bitim YOPILADI (bitta yakuniy natija).
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import pandas as pd

from app.core.constants import Direction, SignalStrength, Timeframe
from app.core.logger import log
from app.ai.signal import Signal


class SignalOutcomeTracker:
    """Ochiq signallarni narxga qarab kuzatib, TP/SL follow-up yuboradi."""

    def __init__(self, feed, journal, renderer, tgbot) -> None:
        self.feed = feed
        self.journal = journal
        self.renderer = renderer
        self.tgbot = tgbot

    # ------------------------------------------------------------------ #
    async def check_all(self) -> None:
        """Barcha ochiq kuzatilayotgan signallarni tekshiradi (bir tsikl)."""
        rows = await asyncio.to_thread(self.journal.active_tracked)
        for row in rows:
            try:
                await self._check_one(row)
            except Exception as e:  # noqa: BLE001
                log.warning(f"Kuzatuv xatosi (id={row['id']} {row['symbol']}): {e}")

    # ------------------------------------------------------------------ #
    async def _check_one(self, row) -> None:
        symbol = row["symbol"]
        tf = Timeframe(row["timeframe"])
        is_buy = row["direction"] == Direction.BUY.value
        entry, sl = row["entry"], row["sl"]
        tp1, tp2, tp3 = row["tp1"], row["tp2"], row["tp3"]
        stage = row["stage"]
        eff_sl = row["eff_sl"]
        last_checked = pd.Timestamp(row["last_checked"]) if row["last_checked"] else None

        # Joriy (shakllanayotgan sham bilan) shamlar — tez aniqlash uchun
        df = await asyncio.to_thread(
            self.feed.get_candles, symbol, tf, 200, True  # include_forming=True
        )
        if df is None or len(df) < 2:
            return
        new_bars = df[df.index > last_checked] if last_checked is not None else df
        if len(new_bars) == 0:
            return

        events: list[tuple[str, str, float]] = []  # (kind, level_name, level_price)
        closed_result: str | None = None

        for ts, bar in new_bars.iterrows():
            hi, lo = float(bar["high"]), float(bar["low"])

            # 1) Himoya stopi (eng ehtiyotkor — avval tekshiriladi)
            stop_hit = (lo <= eff_sl) if is_buy else (hi >= eff_sl)
            if stop_hit:
                closed_result = self._stop_result(stage)
                break

            # 2) TP progressiyasi (bir shamда bir nechta bosqich bo'lishi mumkin)
            if stage == 0 and self._reached(is_buy, hi, lo, tp1):
                stage, eff_sl = 1, entry
                events.append(("TP1", "TP1", tp1))
            if stage == 1 and self._reached(is_buy, hi, lo, tp2):
                stage, eff_sl = 2, tp1
                events.append(("TP2", "TP2", tp2))
            if stage == 2 and self._reached(is_buy, hi, lo, tp3):
                events.append(("TP3", "TP3", tp3))
                closed_result = "TP3 ✅ To'liq maqsad (+3R) 🎉"
                break

        # last_checked = oxirgi YOPILGAN sham (shakllanayotgani qayta tekshirilaveradi)
        last_closed_ts = df.index[-2] if len(df) >= 2 else df.index[-1]
        last_iso = last_closed_ts.isoformat()

        # Progressiya follow-uplari (yopilmagan TP1/TP2)
        for kind, name, level in events:
            if kind in ("TP1", "TP2"):
                await self._send_progress(row, df, kind, level, stage)

        if closed_result is not None:
            await asyncio.to_thread(self.journal.close_tracked, row["id"], closed_result)
            await self._send_close(row, df, closed_result)
            log.info(f"Kuzatuv yakun: {symbol} {row['direction']} -> {closed_result}")
        else:
            await asyncio.to_thread(
                self.journal.update_tracked, row["id"],
                stage=stage, eff_sl=eff_sl, last_checked=last_iso,
            )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _reached(is_buy: bool, hi: float, lo: float, level: float) -> bool:
        return (hi >= level) if is_buy else (lo <= level)

    @staticmethod
    def _stop_result(stage: int) -> str:
        if stage == 0:
            return "SL ❌ Stop Loss (−1R)"
        if stage == 1:
            return "Breakeven ⚖️ (TP1 dan keyin zararsiz)"
        return "TP1'da qulflandi 🟢 (+1R)"

    # ------------------------------------------------------------------ #
    def _rebuild_signal(self, row) -> Signal:
        return Signal(
            symbol=row["symbol"], timeframe=row["timeframe"],
            direction=Direction(row["direction"]), confidence=0,
            strength=SignalStrength.MEDIUM,
            entry=row["entry"], stop_loss=row["sl"], take_profit=row["tp2"],
            tp1=row["tp1"], tp2=row["tp2"], tp3=row["tp3"], risk_reward=2.0,
            price_at_signal=row["entry"], buy_score=0, sell_score=0,
            created_at=datetime.now(),
        )

    async def _chart(self, row, df, title: str) -> str | None:
        try:
            sig = self._rebuild_signal(row)
            return await asyncio.to_thread(self.renderer.render, df, sig, None, title)
        except Exception as e:  # noqa: BLE001
            log.warning(f"Follow-up grafik xatosi: {e}")
            return None

    async def _send_progress(self, row, df, kind: str, level: float, stage: int) -> None:
        arrow = "🟢 BUY" if row["direction"] == Direction.BUY.value else "🔴 SELL"
        sym = f"{row['symbol']} ({row['timeframe']})"
        if kind == "TP1":
            body = (f"🎯 <b>TP1 bajarildi (+1R)!</b>\n{arrow} {sym}\n"
                    f"Narx <code>{level}</code> ga yetdi.\n"
                    f"🛡 Himoya stopi Entry (zararsiz)ga ko'chirildi — endi bu bitim "
                    f"eng yomon holda zararsiz. Qisman foyda olishni o'ylang.")
            title = f"{row['symbol']} {row['timeframe']} — TP1 bajarildi (+1R)"
        else:  # TP2
            body = (f"🎯 <b>TP2 bajarildi (+2R)!</b>\n{arrow} {sym}\n"
                    f"Narx <code>{level}</code> ga yetdi.\n"
                    f"🛡 Himoya stopi TP1 ga ko'chirildi — <b>+1R qulflandi</b>. "
                    f"Keyingi maqsad: TP3.")
            title = f"{row['symbol']} {row['timeframe']} — TP2 bajarildi (+2R)"
        chart = await self._chart(row, df, title)
        await self.tgbot.send_followup(body, chart, reply_to=row["message_id"])

    async def _send_close(self, row, df, result: str) -> None:
        arrow = "🟢 BUY" if row["direction"] == Direction.BUY.value else "🔴 SELL"
        sym = f"{row['symbol']} ({row['timeframe']})"
        if result.startswith("TP3"):
            emoji, note = "🎉", "TP3 — to'liq maqsad! Bitim +3R bilan yopildi."
        elif result.startswith("SL"):
            emoji, note = "🛑", "Stop Loss tegdi. Bitim −1R bilan yopildi. Keyingi imkoniyatni kutamiz."
        elif result.startswith("Breakeven"):
            emoji, note = "⚖️", "TP1 dan keyin narx qaytib zararsiz (Entry) stopga tegdi. Bitim zararsiz yopildi."
        else:  # TP1'da qulflandi
            emoji, note = "🟢", "TP2 gача yetgach narx qaytdi va TP1 himoya stopiga tegdi. Bitim +1R bilan yopildi."
        body = (f"{emoji} <b>Bitim yopildi — {result}</b>\n{arrow} {sym}\n{note}\n"
                f"━━━━━━━━━━━━━━\n⚠️ Demo signal — moliyaviy maslahat emas.")
        title = f"{row['symbol']} {row['timeframe']} — YOPILDI: {result}"
        chart = await self._chart(row, df, title)
        await self.tgbot.send_followup(body, chart, reply_to=row["message_id"])
