"""
TITAN AI — Telegram bot (aiogram 3.x).

Vazifasi:
  - Signalni kanalga/guruhga yuborish: grafik + Grok tahlili + Auto-Trade tugmasi
  - "Auto-Trade" tugmasi bosilganda MT5 demo'da savdo ochish (executor orqali)
  - Natijani xabarga qaytarish

Signal saqlash: pending (xotirada) dict — tugma bosilganda signalni topish uchun.
"""
from __future__ import annotations

import asyncio
import html
import uuid

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery, FSInputFile

from app.core.config import settings
from app.core.constants import Direction
from app.core.logger import log
from app.ai.signal import Signal
from app.execution import TradeExecutor
from app.telegram.keyboards import signal_keyboard, traded_keyboard

CAPTION_LIMIT = 1024  # Telegram rasm izohi (caption) chegarasi


class TitanTelegramBot:
    """TITAN AI Telegram boti."""

    def __init__(self, executor: TradeExecutor | None = None) -> None:
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN .env da yo'q")
        self.bot = Bot(token=settings.telegram_bot_token)
        self.dp = Dispatcher()
        self.executor = executor or TradeExecutor()
        self.pending: dict[str, Signal] = {}     # signal_id -> Signal
        self._register()

    # ------------------------------------------------------------------ #
    #  Handlerlarni ro'yxatga olish
    # ------------------------------------------------------------------ #
    def _register(self) -> None:
        self.dp.callback_query(F.data.startswith("trade:"))(self._on_trade)
        self.dp.callback_query(F.data.startswith("skip:"))(self._on_skip)
        self.dp.callback_query(F.data == "noop")(self._on_noop)

    # ------------------------------------------------------------------ #
    #  Signalni yuborish
    # ------------------------------------------------------------------ #
    async def send_signal(self, signal: Signal, chart_path: str) -> str:
        """Signalni kanalga yuboradi. Signal_id qaytaradi."""
        signal_id = uuid.uuid4().hex[:12]
        self.pending[signal_id] = signal

        caption = self._format_caption(signal)
        await self.bot.send_photo(
            chat_id=settings.telegram_channel_id,
            photo=FSInputFile(chart_path),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=signal_keyboard(signal_id),
        )
        log.info(f"Signal Telegram'ga yuborildi (id={signal_id}): {signal.symbol} {signal.direction.value}")
        return signal_id

    def _format_caption(self, signal: Signal) -> str:
        arrow = "🟢 BUY" if signal.is_buy else "🔴 SELL"
        expl = signal.ai_explanation or "—"
        head = (
            f"{arrow} — <b>{signal.symbol}</b> ({signal.timeframe})\n"
            f"━━━━━━━━━━━━━━\n"
            f"📊 Ishonch: <b>{signal.confidence:.0f}%</b> [{signal.strength.value}]\n"
            f"📍 Entry: <code>{signal.entry}</code>\n"
            f"🛑 Stop Loss: <code>{signal.stop_loss}</code>\n"
            f"🎯 Take Profit: <code>{signal.take_profit}</code>\n"
            f"⚖️ Risk/Reward: 1:{signal.risk_reward:.1f}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🤖 <b>Tahlil:</b>\n"
        )
        tail = "\n━━━━━━━━━━━━━━\n⚠️ Demo signal — moliyaviy maslahat emas."
        room = CAPTION_LIMIT - len(head) - len(tail)
        expl_safe = html.escape(expl)
        if len(expl_safe) > room:
            expl_safe = expl_safe[: room - 1] + "…"
        return head + expl_safe + tail

    # ------------------------------------------------------------------ #
    #  Auto-Trade tugmasi
    # ------------------------------------------------------------------ #
    async def _on_trade(self, cb: CallbackQuery) -> None:
        signal_id = cb.data.split(":", 1)[1]

        # Ruxsat tekshiruvi (admin ID'lar belgilangan bo'lsa)
        if settings.admin_ids and cb.from_user.id not in settings.admin_ids:
            await cb.answer("⛔ Sizda savdo ochish huquqi yo'q.", show_alert=True)
            log.warning(f"Ruxsatsiz trade urinishi: user={cb.from_user.id}")
            return

        signal = self.pending.get(signal_id)
        if signal is None:
            await cb.answer("⏳ Signal eskirgan yoki topilmadi.", show_alert=True)
            return

        await cb.answer("⏳ Savdo ochilmoqda...")
        try:
            # MT5 chaqiruvi sinxron — event loop'ni bloklamaslik uchun alohida thread
            result = await asyncio.to_thread(self.executor.open_signal, signal)
        except Exception as e:  # noqa: BLE001
            log.error(f"Trade xatoligi: {e}")
            await cb.message.reply(f"❌ Xatolik: {html.escape(str(e))}")
            return

        if not result.success:
            await cb.message.reply(
                f"❌ Savdo ochilmadi (retcode={result.retcode}): {result.message}"
            )
            return

        # Muvaffaqiyat — xabarni yangilaymiz
        self.pending.pop(signal_id, None)
        who = cb.from_user.full_name
        await cb.message.edit_reply_markup(reply_markup=traded_keyboard(result.order))
        await cb.message.reply(
            f"✅ <b>Savdo ochildi!</b>\n"
            f"🎫 Ticket: <code>{result.order}</code>\n"
            f"💰 Lot: {result.volume}\n"
            f"📍 Narx: {result.price}\n"
            f"👤 {html.escape(who)}\n"
            f"ℹ️ {html.escape(result.lot_info)}",
            parse_mode=ParseMode.HTML,
        )
        log.info(f"✅ Auto-Trade bajarildi: ticket={result.order} by {who}")

    async def _on_skip(self, cb: CallbackQuery) -> None:
        signal_id = cb.data.split(":", 1)[1]
        self.pending.pop(signal_id, None)
        await cb.answer("O'tkazib yuborildi.")
        await cb.message.edit_reply_markup(reply_markup=None)

    async def _on_noop(self, cb: CallbackQuery) -> None:
        await cb.answer()

    # ------------------------------------------------------------------ #
    #  Ishga tushirish (polling)
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """Botni polling rejimida ishga tushiradi (tugmalar ishlashi uchun)."""
        self.executor.conn.ensure_connected()
        log.info("Telegram bot polling boshlandi. Tugmalar faol.")
        await self.dp.start_polling(self.bot)

    async def close(self) -> None:
        await self.bot.session.close()
