"""Lightweight retrieval-augmented generation helpers."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DocumentChunk:
    """Chunk stored in the knowledge base."""

    text: str
    source_path: str
    profile: str
    section: Optional[str] = None


class KnowledgeStore:
    """Persistent FAISS + SQLite powered knowledge base."""

    def __init__(self, db_path: Path, index_path: Path, embed_model: str) -> None:
        self._db_path = Path(db_path)
        self._index_path = Path(index_path)
        self._embed_model_name = embed_model
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    section TEXT
                )
                """
            )
            conn.commit()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading sentence transformer model %s", self._embed_model_name)
            self._model = SentenceTransformer(self._embed_model_name)
        return self._model

    @property
    def index(self) -> faiss.IndexFlatIP:
        if self._index is None:
            if self._index_path.exists():
                logger.info("Loading FAISS index from %s", self._index_path)
                self._index = faiss.read_index(str(self._index_path))
            else:
                self._index = faiss.IndexFlatIP(self.model.get_sentence_embedding_dimension())
        return self._index

    def reset_index(self) -> None:
        self._index = faiss.IndexFlatIP(self.model.get_sentence_embedding_dimension())

    def add_documents(self, chunks: Sequence[DocumentChunk]) -> None:
        if not chunks:
            return
        embeddings = self.model.encode([chunk.text for chunk in chunks])
        ids: List[int] = []
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.executemany(
                "INSERT INTO documents (text, source_path, profile, section) VALUES (?, ?, ?, ?)",
                [(chunk.text, chunk.source_path, chunk.profile, chunk.section) for chunk in chunks],
            )
            conn.commit()
            ids.extend(range(cursor.lastrowid - len(chunks) + 1, cursor.lastrowid + 1))
        index = self.index
        index.add_with_ids(np.asarray(embeddings, dtype=np.float32), np.asarray(ids, dtype=np.int64))
        faiss.write_index(index, str(self._index_path))

    def rebuild_index(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            rows = list(conn.execute("SELECT id, text FROM documents ORDER BY id"))
        if not rows:
            self.reset_index()
            faiss.write_index(self.index, str(self._index_path))
            return
        ids = np.asarray([row[0] for row in rows], dtype=np.int64)
        texts = [row[1] for row in rows]
        embeddings = self.model.encode(texts)
        index = faiss.IndexFlatIP(self.model.get_sentence_embedding_dimension())
        index.add_with_ids(np.asarray(embeddings, dtype=np.float32), ids)
        self._index = index
        faiss.write_index(index, str(self._index_path))

    def search(self, query: str, top_k: int, profile: Optional[str] = None) -> List[DocumentChunk]:
        if not query.strip():
            return []
        embeddings = self.model.encode([query])
        index = self.index
        if index.ntotal == 0:
            return []
        scores, ids = index.search(np.asarray(embeddings, dtype=np.float32), top_k)
        hits: List[DocumentChunk] = []
        with sqlite3.connect(self._db_path) as conn:
            for doc_id, score in zip(ids[0], scores[0]):
                if doc_id == -1:
                    continue
                row = conn.execute(
                    "SELECT text, source_path, profile, section FROM documents WHERE id = ?", (int(doc_id),)
                ).fetchone()
                if not row:
                    continue
                text, source_path, doc_profile, section = row
                if profile and doc_profile != profile:
                    continue
                hits.append(DocumentChunk(text=text, source_path=source_path, profile=doc_profile, section=section))
        return hits

    def delete_by_source(self, source_path: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM documents WHERE source_path = ?", (source_path,))
            conn.commit()
        self.rebuild_index()


def chunk_text(text: str, chunk_size: int = 600, overlap: int = 80) -> List[str]:
    """Split text into overlapping character based chunks."""

    tokens = text.split()
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for token in tokens:
        if current_len + len(token) >= chunk_size and current:
            chunks.append(" ".join(current))
            current = current[-overlap:]
            current_len = sum(len(t) for t in current)
        current.append(token)
        current_len += len(token)
    if current:
        chunks.append(" ".join(current))
    return chunks


__all__ = ["KnowledgeStore", "DocumentChunk", "chunk_text"]
