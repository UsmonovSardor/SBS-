"""
Bilim bazasi ombori (SQLite) — hujjatlar + bo'laklar + embeddinglar.

DB `data/knowledge.db` (persistent bind-mount) — bot qayta yuklaganда qayta
embedding qilinmaydi. Manba fayllar `knowledge/` papkasi (haqiqat manbai);
DB ulardan hosil bo'ladi (sha bilan o'zgargani aniqlanadi).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np

from app.core.config import BASE_DIR
from app.core.logger import log

KB_PATH = BASE_DIR / "data" / "knowledge.db"


class KnowledgeStore:
    """Bilim bazasi hujjat/bo'lak/embeddinglarini SQLite'da yuritadi."""

    def __init__(self, path: str | None = None) -> None:
        self.path = str(path) if path else str(KB_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS kb_docs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE,      -- knowledge/ papkasiga nisbatan yo'l
                    sha TEXT,              -- fayl mazmuni hashi (o'zgarish aniqlash)
                    title TEXT,
                    added_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS kb_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER,
                    ord INTEGER,           -- hujjat ichidagi tartib
                    text TEXT,
                    dim INTEGER,
                    embedding BLOB         -- float32 vektor (np.tobytes)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON kb_chunks(doc_id)")
        log.debug(f"Bilim bazasi tayyor: {self.path}")

    # ------------------------------------------------------------------ #
    def get_doc(self, path: str) -> sqlite3.Row | None:
        with self._conn() as c:
            return c.execute("SELECT * FROM kb_docs WHERE path=?", (path,)).fetchone()

    def upsert_doc(self, path: str, sha: str, title: str,
                   chunks: list[tuple[str, np.ndarray]]) -> int:
        """Hujjatni (va uning bo'laklarini) qo'shadi/yangilaydi. Eski bo'laklar o'chadi."""
        with self._conn() as c:
            row = c.execute("SELECT id FROM kb_docs WHERE path=?", (path,)).fetchone()
            if row:
                doc_id = row["id"]
                c.execute("UPDATE kb_docs SET sha=?, title=?, added_at=? WHERE id=?",
                          (sha, title, datetime.now().isoformat(), doc_id))
                c.execute("DELETE FROM kb_chunks WHERE doc_id=?", (doc_id,))
            else:
                cur = c.execute(
                    "INSERT INTO kb_docs (path,sha,title,added_at) VALUES (?,?,?,?)",
                    (path, sha, title, datetime.now().isoformat()))
                doc_id = cur.lastrowid
            c.executemany(
                "INSERT INTO kb_chunks (doc_id,ord,text,dim,embedding) VALUES (?,?,?,?,?)",
                [(doc_id, i, text, int(vec.shape[0]),
                  np.asarray(vec, dtype=np.float32).tobytes())
                 for i, (text, vec) in enumerate(chunks)],
            )
        return doc_id

    def delete_doc(self, path: str) -> None:
        with self._conn() as c:
            row = c.execute("SELECT id FROM kb_docs WHERE path=?", (path,)).fetchone()
            if row:
                c.execute("DELETE FROM kb_chunks WHERE doc_id=?", (row["id"],))
                c.execute("DELETE FROM kb_docs WHERE id=?", (row["id"],))

    def all_paths(self) -> set[str]:
        with self._conn() as c:
            return {r["path"] for r in c.execute("SELECT path FROM kb_docs").fetchall()}

    def load_chunks(self) -> list[dict]:
        """Barcha bo'laklarni (matn + vektor + hujjat sarlavhasi) yuklaydi."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT ch.text AS text, ch.dim AS dim, ch.embedding AS emb,
                       d.title AS title, d.path AS path
                FROM kb_chunks ch JOIN kb_docs d ON d.id = ch.doc_id
            """).fetchall()
        out: list[dict] = []
        for r in rows:
            vec = np.frombuffer(r["emb"], dtype=np.float32, count=r["dim"])
            out.append({"text": r["text"], "vec": vec,
                        "title": r["title"], "path": r["path"]})
        return out

    def stats(self) -> dict:
        with self._conn() as c:
            docs = c.execute("SELECT COUNT(*) FROM kb_docs").fetchone()[0]
            chunks = c.execute("SELECT COUNT(*) FROM kb_chunks").fetchone()[0]
        return {"docs": docs, "chunks": chunks}
