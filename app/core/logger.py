"""
TITAN AI — Markazlashtirilgan logging.

loguru asosida: konsolga rangli, `logs/titan.log` fayliga rotatsiya bilan yoziladi.
Ishlatish:
    from app.core.logger import log
    log.info("Xabar")
"""
from __future__ import annotations

import sys

from loguru import logger

from app.core.config import BASE_DIR, settings

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Standart handlerlarni tozalab, o'zimiznikini qo'yamiz
logger.remove()

# Konsol (rangli)
logger.add(
    sys.stderr,
    level=settings.log_level,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# Fayl (rotatsiya + saqlash muddati)
logger.add(
    LOG_DIR / "titan.log",
    level=settings.log_level,
    rotation="10 MB",
    retention="14 days",
    compression="zip",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# Qulay alias
log = logger

__all__ = ["log", "logger"]
