"""
TITAN AI — Maxsus xatoliklar (exceptions).
Har bir tashqi xizmat uchun alohida xatolik turi — muammoni aniq tutish uchun.
"""
from __future__ import annotations


class TitanError(Exception):
    """Barcha TITAN xatoliklarining asosiy klassi."""


class ConfigError(TitanError):
    """Sozlama (.env) bilan bog'liq xatolik."""


class MT5ConnectionError(TitanError):
    """MetaTrader 5 ga ulanish yoki so'rov xatoligi."""


class MarketDataError(TitanError):
    """Bozor ma'lumotlarini olishda xatolik."""


class GrokAPIError(TitanError):
    """Grok (xAI) API xatoligi."""


class TelegramError(TitanError):
    """Telegram bot xatoligi."""


class ExecutionError(TitanError):
    """Savdo ochish/yopishda xatolik (MT5 execution)."""


class RiskError(TitanError):
    """Risk qoidalari buzilganda (masalan kunlik limit)."""
