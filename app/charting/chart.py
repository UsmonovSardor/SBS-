"""
TITAN AI — Signal grafigini chizish.

mplfinance yordamida shamli (candlestick) grafik chizadi va unga:
  - Entry / Stop Loss / Take Profit chiziqlari,
  - Order Block / FVG zonalari (rangli sohalar),
  - sarlavhada signal ma'lumoti
qo'shadi. Natija — PNG fayl (Telegram'ga yuborish uchun).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # GUI'siz (server/headless) rejim

import matplotlib.pyplot as plt  # noqa: E402
import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

from app.core.config import BASE_DIR  # noqa: E402
from app.core.constants import CHART_CANDLES  # noqa: E402
from app.core.logger import log  # noqa: E402
from app.ai.signal import Signal  # noqa: E402

CHARTS_DIR = BASE_DIR / "charts"
CHARTS_DIR.mkdir(exist_ok=True)


@dataclass
class Zone:
    """Grafikda ko'rsatiladigan gorizontal zona (OB yoki FVG)."""
    bottom: float
    top: float
    color: str
    label: str


class ChartRenderer:
    """Signal grafigini PNG qilib chizadi."""

    def __init__(self, candles: int = CHART_CANDLES) -> None:
        self.candles = candles

    def render(
        self,
        df: pd.DataFrame,
        signal: Signal,
        zones: list[Zone] | None = None,
        title: str | None = None,
    ) -> str:
        """Grafik chizib, PNG fayl yo'lini qaytaradi. title berilса sarlavha almashtiriladi."""
        data = df.tail(self.candles).copy()
        zones = zones or []

        # Rang sxemasi (professional dark)
        mc = mpf.make_marketcolors(
            up="#26a69a", down="#ef5350",
            edge="inherit", wick="inherit", volume="in",
        )
        style = mpf.make_mpf_style(
            base_mpf_style="nightclouds",
            marketcolors=mc,
            gridstyle=":",
            facecolor="#131722",
            figcolor="#131722",
        )

        arrow = "▲ BUY" if signal.is_buy else "▼ SELL"
        if title is None:
            title = (
                f"\n{signal.symbol}  {signal.timeframe}   {arrow}   "
                f"conf {signal.confidence:.0f}% [{signal.strength.value}]   RR 1:{signal.risk_reward:.1f}"
            )
        else:
            title = f"\n{title}"

        fig, axes = mpf.plot(
            data,
            type="candle",
            style=style,
            title=title,
            ylabel="Narx",
            returnfig=True,
            figsize=(12, 7),
            tight_layout=True,
            update_width_config={"candle_linewidth": 0.8},
        )
        ax = axes[0]

        # --- Entry / SL / TP1-2-3 chiziqlari ---
        self._hline(ax, signal.entry, "#2962ff", f"Entry {signal.entry}")
        self._hline(ax, signal.stop_loss, "#ef5350", f"SL {signal.stop_loss}")
        if signal.tp1 and signal.tp2 and signal.tp3:
            self._hline(ax, signal.tp1, "#66bb6a", f"TP1 {signal.tp1}")
            self._hline(ax, signal.tp2, "#26a69a", f"TP2 {signal.tp2}")
            self._hline(ax, signal.tp3, "#00897b", f"TP3 {signal.tp3}")
        else:
            self._hline(ax, signal.take_profit, "#26a69a", f"TP {signal.take_profit}")

        # --- Zonalar (OB / FVG) ---
        for z in zones:
            ax.axhspan(z.bottom, z.top, color=z.color, alpha=0.18, zorder=0)

        ax.legend(loc="upper left", fontsize=8, framealpha=0.3)

        # --- Saqlash ---
        ts = signal.created_at.strftime("%Y%m%d_%H%M%S")
        fname = f"{signal.symbol}_{signal.timeframe}_{ts}.png"
        path = CHARTS_DIR / fname
        fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="#131722")
        plt.close(fig)

        log.info(f"Grafik saqlandi: {path}")
        return str(path)

    @staticmethod
    def _hline(ax, price: float, color: str, label: str) -> None:
        ax.axhline(price, color=color, linestyle="--", linewidth=1.2, alpha=0.9, label=label)
