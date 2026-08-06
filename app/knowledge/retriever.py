"""
Retriever — so'rovga (masalan signal konteksti) eng mos bo'laklarni topadi.

Kosinus o'xshashlik + top-k. Bilim bazasi kichik-o'rta (yuzlab-minglab bo'lak)
bo'lgani uchun xotirада brute-force yetarli (indeks shart emas). Bo'laklar
keshlanadi; yangi ingestdan keyin refresh() chaqiriladi.
"""
from __future__ import annotations

import numpy as np

from app.knowledge.store import KnowledgeStore


class Retriever:
    def __init__(self, store: KnowledgeStore, embedder) -> None:
        self.store = store
        self.embedder = embedder
        self._chunks: list[dict] | None = None
        self._matrix: np.ndarray | None = None

    def refresh(self) -> None:
        """Bo'laklarni DBдан qayta yuklaydi (ingestdan keyin chaqiring)."""
        self._chunks = self.store.load_chunks()
        if self._chunks:
            mat = np.vstack([c["vec"] for c in self._chunks]).astype(np.float32)
            norms = np.linalg.norm(mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._matrix = mat / norms
        else:
            self._matrix = None

    def _ensure(self) -> None:
        if self._chunks is None:
            self.refresh()

    def search(self, query: str, top_k: int = 3,
               min_score: float = 0.0) -> list[dict]:
        """Eng mos bo'laklar: [{text, title, path, score}]. Bo'sh bo'lса []."""
        self._ensure()
        if not self._chunks or self._matrix is None:
            return []
        q = np.asarray(self.embedder.embed_query(query), dtype=np.float32)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        q = q / qn
        sims = self._matrix @ q  # kosinus (ikkalasi ham normalangan)
        k = min(top_k, len(sims))
        idx = np.argpartition(-sims, k - 1)[:k]
        idx = idx[np.argsort(-sims[idx])]
        out: list[dict] = []
        for i in idx:
            score = float(sims[i])
            if score < min_score:
                continue
            c = self._chunks[int(i)]
            out.append({"text": c["text"], "title": c["title"],
                        "path": c["path"], "score": round(score, 4)})
        return out
