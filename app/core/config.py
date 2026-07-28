"""
TITAN AI — Markaziy konfiguratsiya.

Barcha sozlamalar `.env` faylidan o'qiladi (pydantic-settings orqali).
Kod ichida hech qachon API kalit yoki parol yozilmaydi.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Loyiha ildizi (bu fayl: app/core/config.py -> 2 pog'ona yuqoriga)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Muhit sozlamalari (.env dan yuklanadi)."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- MetaTrader 5 ---
    mt5_login: int = Field(default=0, alias="MT5_LOGIN")
    mt5_password: str = Field(default="", alias="MT5_PASSWORD")
    mt5_server: str = Field(default="", alias="MT5_SERVER")
    mt5_path: str = Field(default="", alias="MT5_PATH")

    # --- Grok (xAI) ---
    grok_api_key: str = Field(default="", alias="GROK_API_KEY")
    grok_api_base: str = Field(default="https://api.x.ai/v1", alias="GROK_API_BASE")
    grok_model: str = Field(default="grok-4", alias="GROK_MODEL")

    # --- Telegram ---
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: str = Field(default="", alias="TELEGRAM_CHANNEL_ID")
    telegram_admin_ids: str = Field(default="", alias="TELEGRAM_ADMIN_IDS")

    # --- Savdo sozlamalari ---
    trading_mode: str = Field(default="demo", alias="TRADING_MODE")
    default_risk_percent: float = Field(default=1.0, alias="DEFAULT_RISK_PERCENT")
    max_daily_trades: int = Field(default=5, alias="MAX_DAILY_TRADES")
    max_lot: float = Field(default=1.0, alias="MAX_LOT")          # xavfsizlik: maksimal lot
    default_symbols: str = Field(default="EURUSD,XAUUSD", alias="DEFAULT_SYMBOLS")

    # --- Umumiy ---
    timezone: str = Field(default="Asia/Tashkent", alias="TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- Validatorlar ----
    @field_validator("mt5_login", mode="before")
    @classmethod
    def _empty_login_to_zero(cls, v: object) -> object:
        """Bo'sh MT5_LOGIN (=) ni 0 ga aylantiradi (terminal sessiyasiga ulanish uchun)."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return 0
        return v

    # ---- Yordamchi property'lar ----
    @property
    def symbols(self) -> list[str]:
        """Savdo qilinadigan simvollar ro'yxati."""
        return [s.strip().upper() for s in self.default_symbols.split(",") if s.strip()]

    @property
    def admin_ids(self) -> list[int]:
        """Telegram admin ID'lari ro'yxati."""
        out: list[int] = []
        for part in self.telegram_admin_ids.split(","):
            part = part.strip()
            if part.isdigit():
                out.append(int(part))
        return out

    @property
    def is_live(self) -> bool:
        """Real (live) savdo rejimimi? Hozircha faqat demo tavsiya etiladi."""
        return self.trading_mode.lower() == "live"


# Global singleton — butun loyiha shu obyektni ishlatadi
settings = Settings()
