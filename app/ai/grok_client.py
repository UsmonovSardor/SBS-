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
    "tarzda O'ZBEK TILIDA izohlash. Javob 4-6 jumladan oshmasin. "
    "Signal asoslarini mantiqiy bog'lab tushuntir. "
    "Oxirida bitta qisqa risk eslatmasi yoz. Investitsiya maslahati berma — bu tahlil, kafolat emas. "
    "Emoji ishlatma yoki juda oz ishlat. Faqat berilgan ma'lumotga tayan, narx to'qib chiqarma. "
    "\n\nAtamalar (to'g'ri ma'nolari, boshqacha ochib berma):\n"
    "- BOS = Break of Structure (bozor tuzilishining buzilishi, trend davomi signali)\n"
    "- CHoCH = Change of Character (trend o'zgarishining birinchi belgisi)\n"
    "- FVG = Fair Value Gap (uch shamli narx bo'shlig'i / imbalance)\n"
    "- Order Block (OB) = institutsional buyurtma zonasi\n"
    "- Liquidity Sweep = narxning stop-loss'larni yig'ib teskari qaytishi\n"
    "- HH/HL = Higher High / Higher Low (ko'tarilish tuzilishi)\n\n"
    "Agar so'rovда 'BILIM BAZASIDAN' bo'limi berilса — undagi darslarni izohни "
    "boyitish uchun ishlat (tegishli joyида qo'lla), lekin narx/raqamlar faqat "
    "signaldан olinsин, bilim bazasи umumiy nazariy kontekst uchun."
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
    def explain_signal(self, signal: Signal, kb_context: str = "") -> str:
        """
        Signalni professional tilda tushuntiradi.
        kb_context — bilim bazasidan topilган tegishli darslar (A variant, RAG).
        Key sozlanmagan bo'lsa — zaxira (texnik) izoh qaytaradi.
        """
        if not self.is_configured:
            log.warning("AI API key yo'q — zaxira izoh ishlatilmoqda.")
            return self._fallback_explanation(signal)

        prompt = self.build_prompt(signal, kb_context)
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
                raise GrokAPIError("AI bo'sh javob qaytardi")
            log.info(f"AI tushuntirish tayyor ({len(text)} belgi)")
            return text
        except Exception as e:  # noqa: BLE001
            log.error(f"AI xatoligi: {e} — zaxira izohga o'tildi")
            return self._fallback_explanation(signal)

    # ------------------------------------------------------------------ #
    #  Prompt yaratish
    # ------------------------------------------------------------------ #
    def build_prompt(self, signal: Signal, kb_context: str = "") -> str:
        """Signal ma'lumotidan Grok uchun so'rov matnini tayyorlaydi.
        kb_context berilса — 'BILIM BAZASIDAN' bo'limi qo'shiladi (RAG)."""
        votes_txt = "\n".join(
            f"  - {v.strategy} ({v.direction.value}, ishonch {v.confidence:.0f}%): {v.reason}"
            for v in signal.votes
            if v.direction.value != "WAIT"
        )
        arrow = "SOTIB OLISH (BUY)" if signal.is_buy else "SOTISH (SELL)"
        kb_block = f"\n\nBILIM BAZASIDAN (tegishli darslar):\n{kb_context}\n" if kb_context.strip() else ""
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
            f"Signalga asos bo'lgan texnik omillar:\n{votes_txt}\n"
            f"{kb_block}\n"
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
