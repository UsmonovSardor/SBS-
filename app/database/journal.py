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
            # Feature-logging (ML/tahlil poydevori): har signalning 7 ovozi (feature)
            # LONG formatda saqlanadi — yo'qotishsiz, keyin (belgi -> natija) datasetiga
            # pivot qilinadi. Natija tracked_signals.result dan (created_at bo'yicha) olinadi.
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id INTEGER,     -- signals.id ga bog'liq
                    strategy TEXT,         -- trend, structure, order_block, ...
                    direction TEXT,        -- BUY | SELL | WAIT
                    weight REAL,           -- strategiya vazni (ACTIVE_WEIGHTS)
                    confidence REAL        -- shu ovozning ishonchi (0-100)
                )
            """)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_votes_signal ON signal_votes(signal_id)"
            )
            # Signal natijasini kuzatish (TP1/TP2/TP3/SL follow-up uchun)
            c.execute("""
                CREATE TABLE IF NOT EXISTS tracked_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT, timeframe TEXT, direction TEXT, digits INTEGER,
                    entry REAL, sl REAL, tp1 REAL, tp2 REAL, tp3 REAL,
                    message_id INTEGER,
                    stage INTEGER DEFAULT 0,       -- 0=ochiq, 1=TP1, 2=TP2 olindi
                    eff_sl REAL,                   -- joriy (trailing) himoya stopi
                    status TEXT DEFAULT 'OPEN',    -- OPEN | CLOSED
                    result TEXT,
                    last_checked TEXT,
                    opened_at TEXT, closed_at TEXT
                )
            """)
        log.debug(f"Journal tayyor: {self.db}")

    # ------------------------------------------------------------------ #
    #  Signal natijasini kuzatish (tracked_signals)
    # ------------------------------------------------------------------ #
    def add_tracked(self, signal: Signal, message_id: int | None, digits: int,
                    anchor_iso: str) -> int:
        """anchor_iso — signal SHAMINING vaqti (broker/MT5 time). last_checked shu
        vaqtdan boshlanadi, aks holда datetime.now() (konteyner UTC) broker vaqtidan
        farq qilib, signaldan OLDINGI shamlar tekshirilib soxta TP/SL chiqadi."""
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO tracked_signals
                   (symbol,timeframe,direction,digits,entry,sl,tp1,tp2,tp3,
                    message_id,stage,eff_sl,status,last_checked,opened_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,0,?, 'OPEN', ?, ?)""",
                (signal.symbol, signal.timeframe, signal.direction.value, digits,
                 signal.entry, signal.stop_loss, signal.tp1, signal.tp2, signal.tp3,
                 message_id, signal.stop_loss,
                 anchor_iso, signal.created_at.isoformat()),
            )
            return cur.lastrowid

    def active_tracked(self) -> list[sqlite3.Row]:
        with self._conn() as c:
            return c.execute(
                "SELECT * FROM tracked_signals WHERE status='OPEN' ORDER BY id"
            ).fetchall()

    def update_tracked(self, tid: int, *, stage: int, eff_sl: float,
                       last_checked: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE tracked_signals SET stage=?, eff_sl=?, last_checked=? WHERE id=?",
                (stage, eff_sl, last_checked, tid),
            )

    def touch_tracked(self, tid: int, last_checked: str) -> None:
        with self._conn() as c:
            c.execute("UPDATE tracked_signals SET last_checked=? WHERE id=?",
                      (last_checked, tid))

    def close_tracked(self, tid: int, result: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE tracked_signals SET status='CLOSED', result=?, closed_at=? WHERE id=?",
                (result, datetime.now().isoformat(), tid),
            )

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

    def log_features(self, signal_id: int, signal: Signal) -> None:
        """Signalning har bir ovozini (feature) signal_votes'ga yozadi.
        ML/tahlil poydevori — natija bilan bog'lanib (belgi -> natija) dataset beradi."""
        if not signal.votes:
            return
        with self._conn() as c:
            c.executemany(
                """INSERT INTO signal_votes (signal_id,strategy,direction,weight,confidence)
                   VALUES (?,?,?,?,?)""",
                [(signal_id, v.strategy, v.direction.value, v.weight, v.confidence)
                 for v in signal.votes],
            )

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
