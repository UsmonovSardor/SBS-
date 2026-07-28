"""
TITAN AI — MetaTrader 5 ulanish moduli.

MT5 terminaliga ulanadi, account holatini tekshiradi va ulanishni boshqaradi.
Eslatma: bu modul ishlashi uchun kompyuterda MetaTrader 5 terminali
o'rnatilgan bo'lishi va `.env` da demo account ma'lumotlari to'ldirilishi kerak.
"""
from __future__ import annotations

from dataclasses import dataclass

import MetaTrader5 as mt5

from app.core.config import settings
from app.core.exceptions import MT5ConnectionError
from app.core.logger import log


@dataclass
class AccountInfo:
    """MT5 account'ning qisqacha holati."""
    login: int
    server: str
    balance: float
    equity: float
    currency: str
    leverage: int
    margin_free: float
    is_demo: bool


class MT5Connector:
    """
    MetaTrader 5 terminali bilan ulanishni boshqaradi.

    Ishlatish:
        conn = MT5Connector()
        conn.connect()
        info = conn.account_info()
        ...
        conn.disconnect()

    Yoki context manager sifatida:
        with MT5Connector() as conn:
            info = conn.account_info()
    """

    def __init__(self) -> None:
        self._connected: bool = False

    # ------------------------------------------------------------------ #
    #  Ulanish / uzilish
    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        """MT5 terminalini ishga tushirib, account'ga login qiladi."""
        if self._connected:
            return True

        # 1) Terminalni ishga tushirish
        init_kwargs: dict = {}
        if settings.mt5_path:
            init_kwargs["path"] = settings.mt5_path

        if not mt5.initialize(**init_kwargs):
            code, desc = mt5.last_error()
            raise MT5ConnectionError(
                f"MT5 initialize muvaffaqiyatsiz: [{code}] {desc}. "
                f"MetaTrader 5 terminali o'rnatilganini tekshiring."
            )

        # 2) Account'ga login (agar ma'lumotlar berilgan bo'lsa)
        if settings.mt5_login:
            authorized = mt5.login(
                login=settings.mt5_login,
                password=settings.mt5_password,
                server=settings.mt5_server,
            )
            if not authorized:
                code, desc = mt5.last_error()
                mt5.shutdown()
                raise MT5ConnectionError(
                    f"MT5 login muvaffaqiyatsiz (login={settings.mt5_login}, "
                    f"server={settings.mt5_server}): [{code}] {desc}"
                )

        self._connected = True
        info = self.account_info()
        mode = "DEMO" if info.is_demo else "⚠️ REAL"
        log.info(
            f"MT5 ulandi ✅  [{mode}]  login={info.login}  "
            f"server={info.server}  balans={info.balance} {info.currency}"
        )
        return True

    def disconnect(self) -> None:
        """MT5 terminaldan uziladi."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            log.info("MT5 uzildi.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def ensure_connected(self) -> None:
        """Ulanmagan bo'lsa, ulanadi."""
        if not self._connected:
            self.connect()

    # ------------------------------------------------------------------ #
    #  Account ma'lumoti
    # ------------------------------------------------------------------ #
    def account_info(self) -> AccountInfo:
        """Joriy account holatini qaytaradi."""
        self.ensure_connected()
        raw = mt5.account_info()
        if raw is None:
            code, desc = mt5.last_error()
            raise MT5ConnectionError(f"account_info olinmadi: [{code}] {desc}")

        # trade_mode: 0=demo, 1=contest, 2=real
        is_demo = raw.trade_mode != 2
        return AccountInfo(
            login=raw.login,
            server=raw.server,
            balance=raw.balance,
            equity=raw.equity,
            currency=raw.currency,
            leverage=raw.leverage,
            margin_free=raw.margin_free,
            is_demo=is_demo,
        )

    # ------------------------------------------------------------------ #
    #  Context manager
    # ------------------------------------------------------------------ #
    def __enter__(self) -> MT5Connector:
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.disconnect()
