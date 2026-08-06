"""
Semantik embedder — matnni vektorga aylantiradi (local, BEPUL, offline).

fastembed (ONNX runtime — torch KERAK EMAS, yengil). Model birinchi ishlatishда
~130MB yuklanadi (keyin kešда). Model nomi KB_EMBED_MODEL env orqali (default
bge-small-en-v1.5, 384 o'lcham). Ko'p tilli material uchun multilingual modelga
almashtirsa bo'ladi (env orqali).

Test/CI uchun DeterministicEmbedder — model/tarmoq shart emas (hashing trick).
"""
from __future__ import annotations

import numpy as np

from app.core.config import BASE_DIR

# bge modellari uchun tavsiya etilgan so'rov ko'rsatmasi (query != passage)
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# Model keshи persistent `data/` ichida — rebuild'да ~130MB qayta yuklanmaydi.
_CACHE_DIR = str(BASE_DIR / "data" / "fastembed_cache")


class Embedder:
    """fastembed asosidagi haqiqiy embedder (lazy-load)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5",
                 cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir or _CACHE_DIR
        self._model = None

    def _ensure(self):
        if self._model is None:
            from fastembed import TextEmbedding  # og'ir import — lazy
            self._model = TextEmbedding(
                model_name=self.model_name, cache_dir=self.cache_dir)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        m = self._ensure()
        return [np.asarray(v, dtype=np.float32) for v in m.embed(texts)]

    def embed_query(self, text: str) -> np.ndarray:
        m = self._ensure()
        q = _BGE_QUERY_INSTRUCTION + text
        vec = next(iter(m.embed([q])))
        return np.asarray(vec, dtype=np.float32)


class DeterministicEmbedder:
    """Modelsiz, tarmoqsiz embedder (test/zaxira uchun). Hashing trick —
    bir xil so'zlar -> yaqin vektor. Semantik emas, lekin plumbing'ni sinaydi."""

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        import hashlib
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in text.lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim
            v[h] += 1.0
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def embed_documents(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)
