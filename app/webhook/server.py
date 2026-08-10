"""
TITAN AI — TradingView → Telegram webhook (UMUMIY, izolyatsiyalangan).

Vazifa: TradingView Pine `alert()` JSON'ini qabul qilib, uni Telegram guruhga
chiroyli formatda yuboradi. HAR QANDAY simvol/timeframe/yo'nalish uchun ishlaydi.

MUHIM (izolyatsiya):
  - Bu xizmat orchestrator / MT5 / executor'ni IMPORT QILMAYDI.
  - Telegram'ga to'g'ridan-to'g'ri httpx (Bot API) orqali YUBORADI — aiogram
    polling boti bilan hech qanday konflikt yo'q (getUpdates ishlatmaydi).
  - Faqat `settings` (token, kanal, maxfiy so'z) o'qiladi.

Xavfsizlik (fail-closed): TV_WEBHOOK_SECRET .env'da bo'lmasa, xizmat HAR QANDAY
  so'rovni rad etadi (ochiq relay bo'lib qolmasligi uchun).

Kutilgan JSON (Pine `alert()` dan; hammasi ixtiyoriy — moslashuvchan):
  {
    "secret": "<TV_WEBHOOK_SECRET>",   # yoki ?token=... query, yoki X-Secret header
    "symbol": "XAUUSD",
    "tf": "M15",
    "side": "BUY" | "SELL" | "LONG" | "SHORT" | "CLOSE",
    "entry": 2345.6, "sl": 2340.1, "tp": 2354.3,
    "tp1": ..., "tp2": ..., "tp3": ...,        # ixtiyoriy ko'p-maqsad
    "strategy": "Gold Breakout v5",            # ixtiyoriy manba nomi
    "note": "erkin matn",                      # ixtiyoriy qo'shimcha
    "text": "to'liq tayyor matn"               # berilsa — o'sha o'z holicha yuboriladi
  }
"""
from __future__ import annotations

import hmac
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import settings
from app.core.logger import log

_DASHBOARD = Path(__file__).with_name("dashboard.html")

TG_API = "https://api.telegram.org"
_ARROW = {"BUY": "🟢 BUY", "LONG": "🟢 BUY", "SELL": "🔴 SELL", "SHORT": "🔴 SELL"}


# ────────────────────────────────────────────────────────────────────────────
#  Yordamchilar
# ────────────────────────────────────────────────────────────────────────────
def _num(v: Any) -> float | None:
    """Xavfsiz float o'girish (string/None/xato -> None)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    # oqilona aniqlik: butun qism kattaligiga qarab
    if abs(v) >= 100:
        return f"{v:.2f}"
    if abs(v) >= 10:
        return f"{v:.3f}"
    return f"{v:.5f}".rstrip("0").rstrip(".")


def _rr(entry: float | None, sl: float | None, tp: float | None) -> float | None:
    if entry is None or sl is None or tp is None:
        return None
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    return abs(tp - entry) / risk


def _valid_secret(provided: str | None) -> bool:
    """Fail-closed: server maxfiy so'zi bo'lmasa yoki mos kelmasa — rad."""
    expected = settings.tv_webhook_secret
    if not expected:
        return False
    if not provided:
        return False
    return hmac.compare_digest(str(provided), str(expected))


def format_message(data: dict[str, Any]) -> str:
    """Umumiy signal JSON'idan Telegram HTML matni yasaydi (SBS uslubi)."""
    # Tayyor matn berilgan bo'lsa — o'z holicha (faqat HTML-xavfsiz).
    raw = data.get("text")
    if isinstance(raw, str) and raw.strip():
        return html.escape(raw.strip())

    side = str(data.get("side", "")).upper()
    symbol = str(data.get("symbol", "?")).upper()
    tf = str(data.get("tf", data.get("timeframe", "")) or "").upper()
    strat = str(data.get("strategy", "") or "").strip()
    note = str(data.get("note", "") or "").strip()

    entry = _num(data.get("entry"))
    sl = _num(data.get("sl"))
    tp = _num(data.get("tp"))
    tp1, tp2, tp3 = _num(data.get("tp1")), _num(data.get("tp2")), _num(data.get("tp3"))

    # CLOSE / follow-up turi (SL/TP tegdi) — soddaroq xabar
    if side in {"CLOSE", "EXIT", "TP", "SL"}:
        head = f"⚪️ <b>{html.escape(symbol)}</b>{f' ({html.escape(tf)})' if tf else ''} — yopildi"
        body = f"\n{html.escape(note)}" if note else ""
        src = f"\n📡 {html.escape(strat)}" if strat else ""
        return head + body + src + "\n⚠️ Demo signal — moliyaviy maslahat emas."

    arrow = _ARROW.get(side, f"⚪️ {html.escape(side) or 'SIGNAL'}")
    tf_part = f" ({html.escape(tf)})" if tf else ""
    lines = [
        f"{arrow} — <b>{html.escape(symbol)}</b>{tf_part}",
        "━━━━━━━━━━━━━━",
    ]
    if entry is not None:
        lines.append(f"📍 Entry: <code>{_fmt_price(entry)}</code>")
    if sl is not None:
        lines.append(f"🛑 Stop Loss: <code>{_fmt_price(sl)}</code>")
    if any(x is not None for x in (tp1, tp2, tp3)):
        if tp1 is not None:
            lines.append(f"🎯 TP1: <code>{_fmt_price(tp1)}</code>")
        if tp2 is not None:
            lines.append(f"🎯 TP2: <code>{_fmt_price(tp2)}</code>")
        if tp3 is not None:
            lines.append(f"🎯 TP3: <code>{_fmt_price(tp3)}</code>")
    elif tp is not None:
        lines.append(f"🎯 Take Profit: <code>{_fmt_price(tp)}</code>")

    rr = _rr(entry, sl, tp if tp is not None else tp1)
    if rr is not None:
        lines.append(f"📊 R:R 1:{rr:.1f}")
    if note:
        lines.append(f"📝 {html.escape(note)}")
    lines.append("━━━━━━━━━━━━━━")
    src = f"📡 Manba: TradingView — {html.escape(strat)}" if strat else "📡 Manba: TradingView"
    lines.append(src)
    lines.append("⚠️ Demo signal — moliyaviy maslahat emas.")
    return "\n".join(lines)


async def send_telegram(text: str) -> bool:
    """Telegram Bot API'ga to'g'ridan-to'g'ri (aiogram'siz) yuboradi."""
    token = settings.telegram_bot_token
    chat_id = settings.tv_webhook_channel_id or settings.telegram_channel_id
    if not token or not chat_id:
        log.error("Webhook: TELEGRAM_BOT_TOKEN yoki kanal ID yo'q — yuborilmadi.")
        return False
    url = f"{TG_API}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json=payload)
        if r.status_code != 200 or not r.json().get("ok"):
            log.error(f"Webhook: Telegram rad etdi ({r.status_code}): {r.text[:300]}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log.error(f"Webhook: Telegram yuborish xatosi: {e}")
        return False


# ────────────────────────────────────────────────────────────────────────────
#  FastAPI ilova
# ────────────────────────────────────────────────────────────────────────────
def build_app() -> FastAPI:
    app = FastAPI(title="TITAN TV Webhook", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "secret_configured": bool(settings.tv_webhook_secret),
            "channel_set": bool(settings.tv_webhook_channel_id or settings.telegram_channel_id),
            "time": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/stats", response_class=HTMLResponse)
    async def stats_page() -> HTMLResponse:
        try:
            return HTMLResponse(_DASHBOARD.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.error(f"Dashboard o'qish xatosi: {e}")
            return HTMLResponse("<h1>Dashboard topilmadi</h1>", status_code=500)

    @app.get("/stats.json")
    async def stats_json(period: str = Query(default="all")) -> JSONResponse:
        from app.webhook.stats import compute_stats
        try:
            return JSONResponse(compute_stats(period))
        except Exception as e:  # noqa: BLE001
            log.error(f"Statistika hisoblash xatosi: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post("/tv-webhook")
    async def tv_webhook(
        request: Request,
        token: str | None = Query(default=None),
        x_secret: str | None = Header(default=None, alias="X-Secret"),
    ) -> Response:
        # Tanani xavfsiz o'qish: JSON bo'lmasa ham (TV ba'zan text yuboradi) qamrab olamiz
        body_bytes = await request.body()
        data: dict[str, Any]
        try:
            parsed = await request.json()
            data = parsed if isinstance(parsed, dict) else {"text": str(parsed)}
        except Exception:  # noqa: BLE001
            data = {"text": body_bytes.decode("utf-8", "replace")}

        provided = data.get("secret") or token or x_secret
        if not _valid_secret(provided):
            log.warning(f"Webhook: RAD ETILDI (noto'g'ri/yo'q token) ip={request.client.host if request.client else '?'}")
            return Response(status_code=status.HTTP_401_UNAUTHORIZED, content="unauthorized")

        text = format_message(data)
        if not text.strip():
            return Response(status_code=status.HTTP_400_BAD_REQUEST, content="empty")

        ok = await send_telegram(text)
        if not ok:
            return Response(status_code=status.HTTP_502_BAD_GATEWAY, content="telegram failed")
        log.info(f"Webhook: yuborildi — {data.get('symbol','?')} {data.get('side','?')} {data.get('tf','')}")
        return Response(status_code=status.HTTP_200_OK, content="ok")

    return app
