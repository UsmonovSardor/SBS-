"""
TITAN AI — Trading Journal (SQLite).

Manba: TITAN AI TRADING BIBLE, 17-bob (Database) — soddalashtirilgan SQLite versiya.
Signal va savdolar tarixini saqlaydi, statistika beradi. Server o'rnatish shart emas.
(Keyinchalik PostgreSQL'ga o'tish uchun faqat shu modul o'zgaradi.)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.core.config import BASE_DIR
from app.core.logger import log
from app.ai.signal import Signal

DB_PATH = BASE_DIR / "data" / "titan.db"


class Journal:
    """Signal va savdo tarixini SQLite'da yuritadi."""

    def __init__(self) -> None:
        DB_PATH.parent.mkdir(exist_ok=True)
        self.db = str(DB_PATH)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, timeframe TEXT, direction TEXT,
                    confidence REAL, strength TEXT,
                    entry REAL, stop_loss REAL, take_profit REAL, rr REAL,
                    explanation TEXT, created_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket INTEGER, symbol TEXT, direction TEXT,
                    lot REAL, entry REAL, sl REAL, tp REAL,
                    opened_at TEXT, closed_at TEXT,
                    profit REAL DEFAULT 0, status TEXT DEFAULT 'open',
                    signal_id INTEGER
                )
            """)
        log.debug(f"Journal tayyor: {self.db}")

    # ------------------------------------------------------------------ #
    #  Yozish
    # ------------------------------------------------------------------ #
    def log_signal(self, signal: Signal) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO signals
                   (symbol,timeframe,direction,confidence,strength,entry,stop_loss,
                    take_profit,rr,explanation,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (signal.symbol, signal.timeframe, signal.direction.value,
                 signal.confidence, signal.strength.value, signal.entry,
                 signal.stop_loss, signal.take_profit, signal.risk_reward,
                 signal.ai_explanation, signal.created_at.isoformat()),
            )
            return cur.lastrowid

    def log_trade(self, ticket: int, signal: Signal, lot: float, price: float,
                  signal_id: int | None = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO trades
                   (ticket,symbol,direction,lot,entry,sl,tp,opened_at,status,signal_id)
                   VALUES (?,?,?,?,?,?,?,?, 'open', ?)""",
                (ticket, signal.symbol, signal.direction.value, lot, price,
                 signal.stop_loss, signal.take_profit,
                 datetime.now().isoformat(), signal_id),
            )
            return cur.lastrowid

    def close_trade(self, ticket: int, profit: float) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE trades SET status='closed', profit=?, closed_at=? WHERE ticket=? AND status='open'",
                (profit, datetime.now().isoformat(), ticket),
            )

    def sync_closed(self, open_tickets: set[int], profits: dict[int, float]) -> None:
        """MT5'da endi ochiq bo'lmagan savdolarni 'closed' deb belgilaydi."""
        with self._conn() as c:
            rows = c.execute("SELECT ticket FROM trades WHERE status='open'").fetchall()
            for r in rows:
                t = r["ticket"]
                if t not in open_tickets:
                    c.execute(
                        "UPDATE trades SET status='closed', profit=?, closed_at=? WHERE ticket=?",
                        (profits.get(t, 0.0), datetime.now().isoformat(), t),
                    )

    # ------------------------------------------------------------------ #
    #  Statistika
    # ------------------------------------------------------------------ #
    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            trades = c.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            open_n = c.execute("SELECT COUNT(*) FROM trades WHERE status='open'").fetchone()[0]
            closed = c.execute("SELECT COUNT(*) FROM trades WHERE status='closed'").fetchone()[0]
            wins = c.execute("SELECT COUNT(*) FROM trades WHERE status='closed' AND profit>0").fetchone()[0]
            losses = c.execute("SELECT COUNT(*) FROM trades WHERE status='closed' AND profit<=0").fetchone()[0]
            profit = c.execute("SELECT COALESCE(SUM(profit),0) FROM trades WHERE status='closed'").fetchone()[0]
        win_rate = (wins / closed * 100) if closed else 0.0
        return {
            "signals": total, "trades": trades, "open": open_n, "closed": closed,
            "wins": wins, "losses": losses, "win_rate": round(win_rate, 1),
            "total_profit": round(profit, 2),
        }
