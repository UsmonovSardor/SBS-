"""
MT5 ulanishni tekshirish skripti.

Ishga tushirishdan oldin:
  1) Kompyuterda MetaTrader 5 terminali o'rnatilgan bo'lsin
  2) .env faylida MT5_LOGIN, MT5_PASSWORD, MT5_SERVER to'ldirilgan bo'lsin

Ishga tushirish (loyiha ildizidan):
  venv\\Scripts\\python.exe scripts\\test_mt5.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Loyiha ildizini import yo'liga qo'shamiz
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.constants import Timeframe  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.market import DataFeed, MT5Connector  # noqa: E402


def main() -> None:
    conn = MT5Connector()
    try:
        conn.connect()

        # 1) Account holati
        acc = conn.account_info()
        log.info("─── ACCOUNT ───")
        log.info(f"  Login:    {acc.login} ({'DEMO' if acc.is_demo else 'REAL'})")
        log.info(f"  Server:   {acc.server}")
        log.info(f"  Balans:   {acc.balance} {acc.currency}")
        log.info(f"  Equity:   {acc.equity} {acc.currency}")
        log.info(f"  Leverage: 1:{acc.leverage}")

        # 2) Simvol ma'lumoti va narx
        feed = DataFeed()
        for symbol in ["EURUSD", "XAUUSD"]:
            try:
                info = feed.get_symbol_info(symbol)
                tick = feed.get_tick(symbol)
                log.info(f"─── {symbol} ───")
                log.info(f"  Digits: {info.digits}  Spread: {info.spread} punkt")
                log.info(f"  Bid: {tick.bid}  Ask: {tick.ask}")

                # 3) Oxirgi 5 ta M15 sham
                df = feed.get_candles(symbol, Timeframe.M15, count=5)
                log.info(f"  Oxirgi 5 ta M15 sham:\n{df[['open', 'high', 'low', 'close']]}")
            except Exception as e:  # noqa: BLE001
                log.error(f"  {symbol} xatolik: {e}")

        log.info("✅ MT5 test muvaffaqiyatli yakunlandi.")

    except Exception as e:  # noqa: BLE001
        log.error(f"❌ MT5 test xatolik bilan tugadi: {e}")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
