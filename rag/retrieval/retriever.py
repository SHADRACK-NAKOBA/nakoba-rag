"""
rag/retrieval/retriever.py
Advanced Hybrid RAG Retriever.

Implements:
- Semantic (dense) search via vector store
- Metadata filtering (source system, RBAC, date)
- Source context awareness (provenance tagging)
- Re-ranking (live API sources > indexed KB)
- Semantic cache (short-circuit repeated queries)
"""
from __future__ import annotations
import hashlib
import json
import logging
from datetime import datetime, timezone

from rag.vectorstore.store import Document, SearchResult, get_vector_store
from auth.models import UserContext

logger = logging.getLogger(__name__)

# In-memory semantic cache {query_hash: (result, timestamp)}
_semantic_cache: dict[str, tuple[list[SearchResult], float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _cache_key(query: str, filters: dict) -> str:
    raw = json.dumps({"q": query.lower().strip(), "f": filters}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _is_cache_fresh(ts: float) -> bool:
    return (datetime.now(timezone.utc).timestamp() - ts) < CACHE_TTL_SECONDS


class NakobaRetriever:
    """
    Main retriever used by all agents.
    Provides RAG context formatted for the LLM with full provenance.
    """

    def __init__(self):
        self._store = get_vector_store()

    def retrieve(
        self,
        query: str,
        user: UserContext,
        top_k: int = 8,
        source_systems: list[str] | None = None,
        doc_types: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Natural language query
            user: Authenticated user (for RBAC filtering)
            top_k: Number of results to return
            source_systems: Filter to specific source systems
            doc_types: Filter to specific doc types (incident, kb_article, cmdb, etc.)
            use_cache: Whether to use semantic cache
        """
        filters: dict = {}
        if source_systems:
            filters["source_system"] = source_systems
        if doc_types:
            filters["doc_type"] = doc_types
        filters["rbac_allowed_roles"] = user.roles

        # Check cache
        if use_cache:
            key = _cache_key(query, filters)
            if key in _semantic_cache:
                results, ts = _semantic_cache[key]
                if _is_cache_fresh(ts):
                    logger.info("Cache HIT for query: %s", query[:60])
                    return results

        results = self._store.search(query=query, top_k=top_k * 2, filters=filters)

        # Re-rank: prioritise live/recent over static KB
        SOURCE_PRIORITY = {
            "dynatrace": 0, "zabbix": 0, "gcp_observability": 0,
            "sentinel_one": 1, "tenable": 1, "wiz": 1,
            "servicenow": 2, "jira": 2,
            "confluence": 3, "sharepoint": 3, "leanix": 3,
        }
        results.sort(key=lambda r: (
            SOURCE_PRIORITY.get(r.document.source_system, 4),
            -r.score,
        ))
        results = results[:top_k]

        if use_cache:
            _semantic_cache[key] = (results, datetime.now(timezone.utc).timestamp())

        return results

    def format_context(self, results: list[SearchResult], query: str) -> str:
        """Format retrieved docs into LLM context block with full provenance."""
        if not results:
            return "No relevant context found in the knowledge base for this query."

        lines = [f"RETRIEVED CONTEXT for: '{query}'\n{'='*60}"]
        for i, r in enumerate(results, 1):
            d = r.document
            lines.append(
                f"\n[CTX-{i}] SOURCE: {d.source_system.upper()} | "
                f"TYPE: {d.doc_type} | SCORE: {r.score:.3f} | "
                f"TIMESTAMP: {d.timestamp}\n"
                f"URL: {d.source_url}\n"
                f"ENTITIES: {', '.join(d.entity_refs) or 'none'}\n"
                f"{'─'*40}\n"
                f"{d.content}"
            )
        lines.append(f"\n{'='*60}\n")
        return "\n".join(lines)

    def ingest(self, docs: list[Document]) -> None:
        """Add documents to the vector store."""
        self._store.add_documents(docs)
        logger.info("Ingested %d documents", len(docs))


# Singleton
_retriever: NakobaRetriever | None = None


def get_retriever() -> NakobaRetriever:
    global _retriever
    if _retriever is None:
        _retriever = NakobaRetriever()
    return _retriever