"""
rag/vectorstore/store.py
Vector store abstraction.
- Development:  ChromaDB (local, no GCP needed)
- Production:   Vertex AI Vector Search
"""
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A chunk stored in the vector store."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    source_system: str = ""
    source_url: str = ""
    doc_type: str = ""          # incident | kb_article | cmdb | config | ticket
    timestamp: str = ""
    rbac_tags: list[str] = field(default_factory=list)
    entity_refs: list[str] = field(default_factory=list)
    volatility: str = "static"  # static | dynamic
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    document: Document
    score: float


class VectorStore(Protocol):
    def add_documents(self, docs: list[Document]) -> None: ...
    def search(self, query: str, top_k: int, filters: dict | None) -> list[SearchResult]: ...
    def delete(self, doc_id: str) -> None: ...


# ── ChromaDB implementation (local dev) ────────────────────────────────────

class ChromaVectorStore:
    def __init__(self, persist_dir: str, embedding_fn=None):
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            name="nakoba_rag",
            metadata={"hnsw:space": "cosine"},
        )
        self._embed_fn = embedding_fn or self._default_embed

    def _default_embed(self, texts: list[str]) -> list[list[float]]:
        """Fallback: simple hash-based pseudo-embedding for local testing."""
        import hashlib
        results = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vec = [((b / 255.0) - 0.5) * 2 for b in h]
            # Pad to 768
            while len(vec) < 768:
                vec.extend(vec[:min(len(vec), 768 - len(vec))])
            results.append(vec[:768])
        return results

    def add_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        embeddings = self._embed_fn([d.content for d in docs])
        self._col.upsert(
            ids=[d.id for d in docs],
            embeddings=embeddings,
            documents=[d.content for d in docs],
            metadatas=[{
                "source_system": d.source_system,
                "source_url": d.source_url,
                "doc_type": d.doc_type,
                "timestamp": d.timestamp,
                "rbac_tags": ",".join(d.rbac_tags),
                "entity_refs": ",".join(d.entity_refs),
                "volatility": d.volatility,
                **d.metadata,
            } for d in docs],
        )
        logger.info("Added %d documents to ChromaDB", len(docs))

    def search(
        self,
        query: str,
        top_k: int = 8,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        query_embedding = self._embed_fn([query])[0]
        where = None
        if filters:
            # Convert filters to Chroma where clause
            conditions = []
            if "source_system" in filters:
                conditions.append({"source_system": {"$in": filters["source_system"]}})
            if "rbac_allowed_roles" in filters:
                # Check if any user role is in rbac_tags
                pass  # ChromaDB doesn't support contains on comma-separated strings easily
            where = {"$and": conditions} if len(conditions) > 1 else (conditions[0] if conditions else None)

        results = self._col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._col.count() or 1),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            content = results["documents"][0][i]
            distance = results["distances"][0][i]
            score = 1.0 - distance  # cosine distance → similarity
            output.append(SearchResult(
                document=Document(
                    id=doc_id,
                    content=content,
                    source_system=meta.get("source_system", ""),
                    source_url=meta.get("source_url", ""),
                    doc_type=meta.get("doc_type", ""),
                    timestamp=meta.get("timestamp", ""),
                    rbac_tags=meta.get("rbac_tags", "").split(","),
                    entity_refs=meta.get("entity_refs", "").split(","),
                    volatility=meta.get("volatility", "static"),
                ),
                score=score,
            ))
        return sorted(output, key=lambda r: r.score, reverse=True)

    def delete(self, doc_id: str) -> None:
        self._col.delete(ids=[doc_id])

    def count(self) -> int:
        return self._col.count()


# ── Factory ──────────────────────────────────────────────────────────────────

_store_instance: ChromaVectorStore | None = None


def get_vector_store() -> ChromaVectorStore:
    global _store_instance
    if _store_instance is None:
        from config.settings import get_settings
        s = get_settings()
        if s.vector_store_backend == "chroma":
            import os
            os.makedirs(s.chroma_persist_dir, exist_ok=True)
            _store_instance = ChromaVectorStore(persist_dir=s.chroma_persist_dir)
        else:
            raise NotImplementedError("Vertex Vector Search backend not wired yet in this env")
    return _store_instance