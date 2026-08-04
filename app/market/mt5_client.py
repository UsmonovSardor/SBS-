"""
TITAN AI — MT5 klient tanlagichi (Windows nativ  yoki  Linux/Docker ko'prigi).

Butun loyiha MT5'ga faqat SHU modul orqali murojaat qiladi:

    from app.market.mt5_client import mt5

Ish rejimi env orqali tanlanadi:
  • MT5_HOST bo'sh   -> nativ `MetaTrader5` paketi (Windows'da terminal bilan).
  • MT5_HOST berilgan -> mt5linux ko'prigi (Linux VPS + Docker; Wine ichidagi
    MetaTrader5 serverga RPyC orqali ulanadi). mt5linux MetaTrader5 API'sini
    AYNAN taqlid qiladi (initialize/login/copy_rates_from_pos/order_send/...),
    shu sabab strategiya va data_feed kodiga tegilmaydi.

Bu qatlam Windows'ga bog'liqlikni bitta joyga jamlaydi — qolgan kod bir xil.
"""
from __future__ import annotations

import os

_HOST = os.environ.get("MT5_HOST", "").strip()
_PORT = int(os.environ.get("MT5_PORT", "8001"))

if _HOST:
    # Linux/Docker: Wine ichidagi MT5 serverga RPyC ko'prigi orqali ulanamiz.
    import rpyc as _rpyc
    from mt5linux import MetaTrader5 as _MT5Bridge

    # Wine ichidagi MT5 birinchi import/initialize SEKIN bo'lishi mumkin
    # (sovuq start ~60s). RPyC default 30s timeout'ini oshiramiz, aks holda
    # "AsyncResultTimeout: result expired" bilan yiqiladi.
    _rpyc.core.protocol.DEFAULT_CONFIG["sync_request_timeout"] = int(
        os.environ.get("MT5_RPYC_TIMEOUT", "180")
    )

    mt5 = _MT5Bridge(host=_HOST, port=_PORT)
    IS_BRIDGE = True
else:
    # Windows nativ: MetaTrader5 terminali shu mashinada o'rnatilgan bo'lishi kerak.
    import MetaTrader5 as mt5  # type: ignore

    IS_BRIDGE = False
