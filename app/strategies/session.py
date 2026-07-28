"""
TITAN AI — ICT Kill Zones (savdo sessiyalari).

Manba: TITAN AI TRADING BIBLE, 35.7 (Kill Zones).
Bozor kun davomida har xil faollikda bo'ladi. Institutsional harakatlar ko'pincha
London va New York ochilish "kill zone"larida sodir bo'ladi. Signal shu vaqtларда
kuchliroq, sust (Osiyo) sessiyada esa kuchsizroq hisoblanadi.

Vaqt UTC bo'yicha hisoblanadi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SessionInfo:
    name: str
    in_killzone: bool
    factor: float          # confidence ko'paytuvchisi (>1 kuchaytiradi, <1 pasaytiradi)
    is_weekend: bool = False


# Kill zone'lar (UTC soatlar)
LONDON_KZ = (7, 10)
NY_KZ = (12, 15)
ASIAN_QUIET = (22, 6)   # sust sessiya (kechasi kesib o'tadi)


def current_session(now: datetime | None = None) -> SessionInfo:
    """Joriy sessiyani va confidence ko'paytuvchisini qaytaradi."""
    now = now or datetime.now(timezone.utc)
    h = now.hour
    weekday = now.weekday()  # 0=dushanba ... 5=shanba, 6=yakshanba

    # Dam olish kunlari forex yopiq (shanba to'liq, yakshanba 22:00 UTC gacha)
    is_weekend = weekday == 5 or (weekday == 6 and h < 22) or (weekday == 4 and h >= 22)

    if LONDON_KZ[0] <= h < LONDON_KZ[1]:
        return SessionInfo("London Kill Zone", True, 1.1, is_weekend)
    if NY_KZ[0] <= h < NY_KZ[1]:
        return SessionInfo("New York Kill Zone", True, 1.1, is_weekend)
    # Osiyo sust sessiyasi (22:00–06:00 UTC)
    if h >= ASIAN_QUIET[0] or h < ASIAN_QUIET[1]:
        return SessionInfo("Osiyo (sust)", False, 0.9, is_weekend)
    return SessionInfo("Oraliq sessiya", False, 1.0, is_weekend)
