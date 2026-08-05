"""
TITAN AI — Institutional Volume Engine.

Manba: TITAN AI TRADING BIBLE, 7-bob (Institutional Volume Engine).

Asosiy g'oya (7.1): "Narx — natija, Volume — sabab." Institutsiyalar katta
orderni bo'laklab kiritadi; bu tick volume'da spike sifatida ko'rinadi.

Forex real volume bermaydi (7.4) — shuning uchun TICK VOLUME ishlatiladi (7.3).

Bu modul ovoz emas, TASDIQLASH/REJECT filtri sifatida ishlatiladi (14-bob AI
Reject Engine ruhida):
  • Volume Spike (7.5): oxirgi sham hajmi o'rtachadan >= spike_ratio marta.
  • Volume Confirmation (7.6): signal yo'nalishi hajm bilan quvvatlanadimi.
  • Fake Breakout (7.7): breakout bor, hajm YO'Q -> signal REJECT.
  • Exhaustion (7.8): narx yangi cho'qqi, hajm tushmoqda -> trend zaif (ogohlantirish).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from app.core.constants import Direction


class VolumeState(str, Enum):
    SPIKE = "SPIKE"          # o'rtachadan sezilarli yuqori (institutsional kirish)
    NORMAL = "NORMAL"
    LOW = "LOW"              # past hajm (fake breakout xavfi)
    EXHAUSTION = "EXHAUSTION"  # narx cho'qqi yangilaydi, hajm tushadi


@dataclass
class VolumeResult:
    state: VolumeState
    ratio: float                 # oxirgi hajm / o'rtacha hajm
    candle_dir: Direction        # oxirgi sham yo'nalishi (BUY=bull, SELL=bear)
    reason: str

    @property
    def is_spike(self) -> bool:
        return self.state == VolumeState.SPIKE


class VolumeStrategy:
    """Tick-volume asosida institutsional ishtirokni baholaydi."""

    def __init__(
        self,
        lookback: int = 20,
        spike_ratio: float = 1.8,
        low_ratio: float = 0.7,
        min_confirm_ratio: float = 1.0,
    ) -> None:
        self.lookback = lookback
        self.spike_ratio = spike_ratio
        self.low_ratio = low_ratio
        self.min_confirm_ratio = min_confirm_ratio

    def _avg_volume(self, vol: pd.Series) -> float:
        prev = vol.iloc[-1 - self.lookback:-1]  # oxirgi shamdan oldingi lookback
        m = float(prev.mean()) if len(prev) else 0.0
        return m or 1e-9

    def evaluate(self, df: pd.DataFrame) -> VolumeResult:
        if "tick_volume" not in df.columns or len(df) < self.lookback + 2:
            return VolumeResult(VolumeState.NORMAL, 1.0, Direction.WAIT,
                                "hajm ma'lumoti yetarli emas")
        vol = df["tick_volume"].astype(float)
        avg = self._avg_volume(vol)
        ratio = float(vol.iloc[-1]) / avg

        o = float(df["open"].iloc[-1])
        c = float(df["close"].iloc[-1])
        candle_dir = Direction.BUY if c > o else (Direction.SELL if c < o else Direction.WAIT)

        # Exhaustion: narx yangi cho'qqi/tub, lekin hajm oldingidan past
        recent_high = float(df["high"].iloc[-6:-1].max())
        recent_low = float(df["low"].iloc[-6:-1].min())
        new_extreme = (float(df["high"].iloc[-1]) > recent_high or
                       float(df["low"].iloc[-1]) < recent_low)
        vol_declining = float(vol.iloc[-1]) < float(vol.iloc[-3:-1].mean())
        if new_extreme and vol_declining and ratio < 1.0:
            return VolumeResult(VolumeState.EXHAUSTION, round(ratio, 2), candle_dir,
                                f"exhaustion: yangi ekstremum, hajm tushmoqda (x{ratio:.2f})")

        if ratio >= self.spike_ratio:
            return VolumeResult(VolumeState.SPIKE, round(ratio, 2), candle_dir,
                                f"volume spike x{ratio:.2f} ({candle_dir.value})")
        if ratio <= self.low_ratio:
            return VolumeResult(VolumeState.LOW, round(ratio, 2), candle_dir,
                                f"past hajm x{ratio:.2f} (fake breakout xavfi)")
        return VolumeResult(VolumeState.NORMAL, round(ratio, 2), candle_dir,
                            f"normal hajm x{ratio:.2f}")

    def confirms(self, df: pd.DataFrame, direction: Direction) -> tuple[bool, str]:
        """
        Signal `direction` hajm bilan tasdiqlanadimi (7.6/7.7)?
        Reject shartlari:
          • past hajm (LOW) -> fake breakout, tasdiqlanmaydi.
          • exhaustion signal yo'nalishiga qarshi -> tasdiqlanmaydi.
        """
        res = self.evaluate(df)
        if res.state == VolumeState.LOW or res.ratio < self.min_confirm_ratio:
            return False, f"hajm past (x{res.ratio:.2f}) — fake breakout, tasdiqlanmadi"
        if res.state == VolumeState.EXHAUSTION and res.candle_dir == direction:
            return False, "exhaustion — trend zaiflashmoqda, tasdiqlanmadi"
        return True, f"hajm tasdiqladi ({res.state.value} x{res.ratio:.2f})"
