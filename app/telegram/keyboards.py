"""
TITAN AI — Telegram inline tugmalari.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def signal_keyboard(signal_id: str) -> InlineKeyboardMarkup:
    """Signal ostidagi tugmalar: Auto-Trade va O'tkazib yuborish."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟢 Auto-Trade (savdo ochish)",
                    callback_data=f"trade:{signal_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏭ O'tkazib yuborish",
                    callback_data=f"skip:{signal_id}",
                ),
            ],
        ]
    )


def traded_keyboard(ticket: int) -> InlineKeyboardMarkup:
    """Savdo ochilgandan keyingi holat (tugma bosilmaydigan)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Savdo ochildi #{ticket}", callback_data="noop")]
        ]
    )
