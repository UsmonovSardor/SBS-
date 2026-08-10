"""
TITAN AI — Telegram inline tugmalari.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings


def _stats_button() -> list[InlineKeyboardButton]:
    """STATS_URL berilgan bo'lsa — 'Statistika' URL tugmasi (aks holda bo'sh)."""
    if settings.stats_url:
        return [InlineKeyboardButton(text="📊 Statistika", url=settings.stats_url)]
    return []


def signal_keyboard(signal_id: str) -> InlineKeyboardMarkup:
    """Signal ostidagi tugmalar: Auto-Trade, O'tkazib yuborish, (Statistika)."""
    rows = [
        [InlineKeyboardButton(text="🟢 Auto-Trade (savdo ochish)", callback_data=f"trade:{signal_id}")],
        [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"skip:{signal_id}")],
    ]
    stats = _stats_button()
    if stats:
        rows.append(stats)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def traded_keyboard(ticket: int) -> InlineKeyboardMarkup:
    """Savdo ochilgandan keyingi holat + (Statistika)."""
    rows = [[InlineKeyboardButton(text=f"✅ Savdo ochildi #{ticket}", callback_data="noop")]]
    stats = _stats_button()
    if stats:
        rows.append(stats)
    return InlineKeyboardMarkup(inline_keyboard=rows)
