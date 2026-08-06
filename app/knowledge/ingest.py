"""
Ingest — `knowledge/` papkasidagi fayllarni bo'laklarga bo'lib, embedding bilan
DB'ga indekslaydi. O'zgarmagan fayllar (sha bir xil) qayta embedding qilinmaydi.
O'chirilgan fayllar DB'dan ham o'chadi.

Ishga tushirish (server yoki lokal):
    python -m app.knowledge.ingest
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.config import BASE_DIR
from app.core.logger import log
from app.knowledge.store import KnowledgeStore
from app.knowledge.embedder import Embedder

KB_DIR = BASE_DIR / "knowledge"
SUFFIXES = {".md", ".txt", ".markdown"}


def chunk_text(text: str, max_chars: int = 800, overlap: int = 150) -> list[str]:
    """Matnni ma'noli bo'laklarga bo'ladi (paragraf chegarasini hurmat qiladi)."""
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if len(cur) + len(p) + 2 <= max_chars:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
                cur = ""
            if len(p) <= max_chars:
                cur = p
            else:  # juda uzun paragraf — belgilar bo'yicha bo'lish (overlap bilan)
                step = max(1, max_chars - overlap)
                for i in range(0, len(p), step):
                    chunks.append(p[i:i + max_chars])
    if cur:
        chunks.append(cur)
    return chunks


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _title(path: Path, text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:120]
    return path.stem


def ingest_folder(store: KnowledgeStore, embedder, folder: Path | None = None) -> dict:
    """knowledge/ ni skanlab DBни sinxronlaydi. {added, updated, skipped, removed, chunks} qaytaradi."""
    folder = folder or KB_DIR
    folder.mkdir(exist_ok=True)
    stats = {"added": 0, "updated": 0, "skipped": 0, "removed": 0, "chunks": 0}

    seen: set[str] = set()
    for fp in sorted(folder.rglob("*")):
        if not fp.is_file() or fp.suffix.lower() not in SUFFIXES:
            continue
        # README / _ bilan boshlanган fayllar = ko'rsatma/meta, bilim emas — o'tkazamiz
        if fp.stem.lower() == "readme" or fp.name.startswith("_"):
            continue
        rel = fp.relative_to(folder).as_posix()
        seen.add(rel)
        text = fp.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        sha = _sha(text)
        existing = store.get_doc(rel)
        if existing and existing["sha"] == sha:
            stats["skipped"] += 1
            continue
        chunks = chunk_text(text)
        vecs = embedder.embed_documents(chunks)
        store.upsert_doc(rel, sha, _title(fp, text), list(zip(chunks, vecs)))
        stats["chunks"] += len(chunks)
        stats["updated" if existing else "added"] += 1
        log.info(f"KB indekslandi: {rel} ({len(chunks)} bo'lak)")

    # papkадан o'chirilgan hujjatlarni DBдан ham olib tashlaymiz
    for path in store.all_paths() - seen:
        store.delete_doc(path)
        stats["removed"] += 1
        log.info(f"KB o'chirildi (fayl yo'q): {path}")

    return stats


def main() -> None:
    store = KnowledgeStore()
    embedder = Embedder(model_name=_model_name())
    stats = ingest_folder(store, embedder)
    total = store.stats()
    log.info(f"KB ingest tugadi: {stats} | jami {total}")
    print(f"Ingest: {stats}")
    print(f"Bilim bazasi: {total['docs']} hujjat, {total['chunks']} bo'lak")


def _model_name() -> str:
    try:
        from app.core.config import settings
        return getattr(settings, "kb_embed_model", "BAAI/bge-small-en-v1.5")
    except Exception:  # noqa: BLE001
        return "BAAI/bge-small-en-v1.5"


if __name__ == "__main__":
    main()
