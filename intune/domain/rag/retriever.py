"""Retrieval logic built on top of a vector index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ...core.events import RetrievedContext

try:  # pragma: no cover - optional dependency
    import chromadb
except Exception:  # pragma: no cover
    chromadb = None  # type: ignore


@dataclass(slots=True)
class RetrieverConfig:
    index_path: Path
    top_k: int


class KnowledgeBaseRetriever:
    """Retrieve knowledge snippets either from Chroma or plain text files."""

    def __init__(self, config: RetrieverConfig) -> None:
        self._config = config
        self._client = None
        if chromadb is not None:
            try:
                self._client = chromadb.PersistentClient(path=str(config.index_path))
            except Exception:
                self._client = None

    def retrieve(self, query: str) -> Sequence[RetrievedContext]:
        if not query.strip():
            return []
        if self._client is None:
            return self._fallback(query)
        collection = self._client.get_or_create_collection("intune")
        result = collection.query(query_texts=[query], n_results=self._config.top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        contexts: list[RetrievedContext] = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            source = Path(meta.get("source", "unknown.txt")) if isinstance(meta, dict) else Path("unknown.txt")
            contexts.append(RetrievedContext(source_path=source, score=float(dist), content=str(doc)))
        return contexts

    def _fallback(self, query: str) -> Sequence[RetrievedContext]:
        contexts: list[RetrievedContext] = []
        if not self._config.index_path.exists():
            return contexts
        for path in self._config.index_path.glob("**/*.txt"):
            try:
                text = path.read_text(encoding="utf8")
            except OSError:
                continue
            if query.lower() in text.lower():
                contexts.append(RetrievedContext(source_path=path, score=0.0, content=text[:400]))
            if len(contexts) >= self._config.top_k:
                break
        return contexts


__all__ = ["RetrieverConfig", "KnowledgeBaseRetriever"]
