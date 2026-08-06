"""
TITAN AI — Bilim bazasi (Knowledge Base / RAG).

Manba: TITAN AI TRADING BIBLE, 14-bob (AI Decision Core) + 29-bob (ML/AI).

Foydalanuvchi `knowledge/` papkasiga strategiya/dars/fact fayllarini (.md/.txt)
tashlaydi. Ular bo'laklarga bo'linib, semantik embedding bilan `data/knowledge.db`
ga indekslanadi. Signal kelganда mos darslar qidirib topiladi va:
  - Groq izohига qo'shiladi (A variant — ta'lim),
  - kelajakда AI filtr (B) yoki kod-qoida (C) uchun manba bo'ladi.

Muhim: bilim bazasi o'zi savdo SIFATINI o'zgartirmaydi (matn != edge). U ta'lim
va tahlil poydevori. Sifat faqat kodlangan+keng testda tasdiqlangan qoida orqali
o'zgaradi (C variant).
"""
from app.knowledge.store import KnowledgeStore
from app.knowledge.embedder import Embedder
from app.knowledge.retriever import Retriever
from app.knowledge.ingest import ingest_folder, chunk_text

__all__ = [
    "KnowledgeStore", "Embedder", "Retriever", "ingest_folder", "chunk_text",
]
