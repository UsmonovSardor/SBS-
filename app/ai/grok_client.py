"""
TITAN AI — Grok (xAI) mijozi.

Fusion Engine bergan signalni Grok orqali professional, tabiiy tilda
(o'zbekcha) tushuntiradi — "nimaga asoslanib shu qaror qabul qilindi".

Grok API OpenAI-mos: openai SDK bilan base_url=https://api.x.ai/v1 orqali ishlaydi.
Agar GROK_API_KEY .env da bo'lmasa — mijoz "sozlanmagan" holatda bo'ladi va
oddiy zaxira (fallback) izoh qaytaradi (butun tizim baribir ishlayveradi).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import GrokAPIError
from app.core.logger import log
from app.ai.signal import Signal

SYSTEM_PROMPT = (
    "Sen — TITAN AI nomli institutsional darajadagi Forex/Gold trading tahlilchisisan. "
    "Sening vazifang: berilgan texnik signalni professional, ishonchli va TUSHUNARLI "
    "tarzda O'ZBEK TILIDA izohlash. Smart Money Concepts (BOS, CHoCH, Order Block, FVG, "
    "Liquidity Sweep) atamalaridan foydalanma qo'rqma, lekin ularni qisqa izohlab ket. "
    "Javob 4-6 jumladan oshmasin. Signal asoslarini mantiqiy bog'lab tushuntir. "
    "Oxirida bitta qisqa risk eslatmasi yoz. Investitsiya maslahati berma — bu tahlil, kafolat emas. "
    "Emoji ishlatma yoki juda oz ishlat. Faqat berilgan ma'lumotga tayan, narx to'qib chiqarma."
)


class GrokClient:
    """Grok (xAI) API bilan ishlovchi mijoz."""

    def __init__(self) -> None:
        self._client = None  # dangasa (lazy) yaratiladi

    @property
    def is_configured(self) -> bool:
        """GROK_API_KEY .env da mavjudmi."""
        return bool(settings.grok_api_key.strip())

    def _get_client(self):
        """OpenAI-mos mijozni faqat kerak bo'lganda yaratadi."""
        if self._client is None:
            from openai import OpenAI  # import shu yerda — key yo'q bo'lsa yuklamaslik uchun

            self._client = OpenAI(
                api_key=settings.grok_api_key,
                base_url=settings.grok_api_base,
            )
        return self._client

    # ------------------------------------------------------------------ #
    #  Signalni tushuntirish
    # ------------------------------------------------------------------ #
    def explain_signal(self, signal: Signal) -> str:
        """
        Signalni professional tilda tushuntiradi.
        Key sozlanmagan bo'lsa — zaxira (texnik) izoh qaytaradi.
        """
        if not self.is_configured:
            log.warning("Grok API key yo'q — zaxira izoh ishlatilmoqda.")
            return self._fallback_explanation(signal)

        prompt = self.build_prompt(signal)
        try:
            client = self._get_client()
            resp = client.chat.completions.create(
                model=settings.grok_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=500,
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                raise GrokAPIError("Grok bo'sh javob qaytardi")
            log.info(f"Grok tushuntirish tayyor ({len(text)} belgi)")
            return text
        except Exception as e:  # noqa: BLE001
            log.error(f"Grok xatoligi: {e} — zaxira izohga o'tildi")
            return self._fallback_explanation(signal)

    # ------------------------------------------------------------------ #
    #  Prompt yaratish
    # ------------------------------------------------------------------ #
    def build_prompt(self, signal: Signal) -> str:
        """Signal ma'lumotidan Grok uchun so'rov matnini tayyorlaydi."""
        votes_txt = "\n".join(
            f"  - {v.strategy} ({v.direction.value}, ishonch {v.confidence:.0f}%): {v.reason}"
            for v in signal.votes
            if v.direction.value != "WAIT"
        )
        arrow = "SOTIB OLISH (BUY)" if signal.is_buy else "SOTISH (SELL)"
        return (
            f"Quyidagi savdo signalini tushuntir:\n\n"
            f"Instrument: {signal.symbol}\n"
            f"Taymfrejm: {signal.timeframe}\n"
            f"Yo'nalish: {arrow}\n"
            f"Ishonch (confidence): {signal.confidence:.0f}% ({signal.strength.value})\n"
            f"Kirish narxi (Entry): {signal.entry}\n"
            f"Stop Loss: {signal.stop_loss}\n"
            f"Take Profit: {signal.take_profit}\n"
            f"Risk/Reward: 1:{signal.risk_reward:.1f}\n\n"
            f"Signalga asos bo'lgan texnik omillar:\n{votes_txt}\n\n"
            f"Shu omillarni mantiqiy bog'lab, nima uchun bu yo'nalish tanlanganini izohlab ber."
        )

    # ------------------------------------------------------------------ #
    #  Zaxira izoh (key yo'q yoki xatolik bo'lganda)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fallback_explanation(signal: Signal) -> str:
        arrow = "ko'tarilish (BUY)" if signal.is_buy else "tushish (SELL)"
        factors = ", ".join(
            v.reason for v in signal.votes if v.direction == signal.direction
        )
        return (
            f"{signal.symbol} ({signal.timeframe}) bo'yicha {arrow} signali. "
            f"Ishonch darajasi {signal.confidence:.0f}% ({signal.strength.value}). "
            f"Asoslar: {factors}. "
            f"Kirish {signal.entry}, himoya (SL) {signal.stop_loss}, maqsad (TP) {signal.take_profit}, "
            f"Risk/Reward 1:{signal.risk_reward:.1f}. "
            f"Eslatma: bu texnik tahlil, moliyaviy kafolat emas — riskni nazorat qiling."
        )
