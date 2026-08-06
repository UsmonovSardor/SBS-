"""Bilim bazasi (RAG poydevori): ingest + retrieve testlari (modelsiz)."""
from __future__ import annotations

from app.knowledge.store import KnowledgeStore
from app.knowledge.embedder import DeterministicEmbedder
from app.knowledge.retriever import Retriever
from app.knowledge.ingest import ingest_folder, chunk_text


def _write(folder, name, text):
    p = folder / name
    p.write_text(text, encoding="utf-8")
    return p


def test_chunk_text_respects_paragraphs():
    text = "Birinchi paragraf.\n\nIkkinchi paragraf.\n\nUchinchi."
    chunks = chunk_text(text, max_chars=25)
    assert len(chunks) >= 2
    assert all(c.strip() for c in chunks)


def test_ingest_and_retrieve(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    _write(kb, "ob.md", "# Order Block\n\nOrder block institutsional zona. "
                        "Narx qaytib retest qiladi.")
    _write(kb, "fvg.md", "# Fair Value Gap\n\nFVG uch shamli bo'shliq. "
                         "Narx uni to'ldirishga qaytadi.")

    store = KnowledgeStore(path=str(tmp_path / "kb.db"))
    emb = DeterministicEmbedder()
    stats = ingest_folder(store, emb, folder=kb)
    assert stats["added"] == 2
    assert store.stats()["chunks"] >= 2

    r = Retriever(store, emb)
    hits = r.search("order block institutsional zona retest", top_k=2)
    assert hits, "hech qanday bo'lak topilmadi"
    # eng mos bo'lak Order Block hujjatidan bo'lishi kerak (so'z mosligi)
    assert hits[0]["path"] == "ob.md"
    assert hits[0]["score"] > 0


def test_reingest_skips_unchanged(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    _write(kb, "a.md", "# A\n\nStrategiya matni bir.")
    store = KnowledgeStore(path=str(tmp_path / "kb.db"))
    emb = DeterministicEmbedder()
    ingest_folder(store, emb, folder=kb)
    stats2 = ingest_folder(store, emb, folder=kb)   # o'zgarmadi
    assert stats2["skipped"] == 1
    assert stats2["added"] == 0


def test_deleted_file_removed_from_db(tmp_path):
    kb = tmp_path / "knowledge"
    kb.mkdir()
    p = _write(kb, "temp.md", "# Temp\n\nVaqtinchalik dars.")
    store = KnowledgeStore(path=str(tmp_path / "kb.db"))
    emb = DeterministicEmbedder()
    ingest_folder(store, emb, folder=kb)
    assert store.stats()["docs"] == 1
    p.unlink()
    stats = ingest_folder(store, emb, folder=kb)
    assert stats["removed"] == 1
    assert store.stats()["docs"] == 0
