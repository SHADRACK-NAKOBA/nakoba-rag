"""
data_plane/normalization/normalizer.py

Entity Normalization & Metadata Enrichment.
Resolves naming conflicts across all source systems:
  Zabbix "Host" == ServiceNow "CI" == Device42 "Asset" == Dynatrace "Entity"

Also chunks long content and attaches RBAC + provenance metadata.
"""
from __future__ import annotations
import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from rag.vectorstore.store import Document

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200      # chars per chunk
CHUNK_OVERLAP = 150    # chars overlap


# RBAC tags per source system
SOURCE_RBAC: dict[str, list[str]] = {
    "zabbix":          ["l1_support", "l2_support", "l3_support", "it_admin"],
    "dynatrace":       ["l2_support", "l3_support", "it_admin"],
    "servicenow":      ["l1_support", "l2_support", "l3_support", "it_admin"],
    "jira":            ["l1_support", "l2_support", "l3_support", "developer", "it_admin"],
    "confluence":      ["l1_support", "l2_support", "l3_support", "developer", "finance", "it_admin"],
    "sharepoint":      ["l1_support", "l2_support", "l3_support", "developer", "finance", "it_admin"],
    "wiz":             ["security", "security_admin"],
    "tenable":         ["security", "security_admin"],
    "sentinel_one":    ["security", "security_admin"],
    "leanix":          ["l2_support", "l3_support", "finance", "it_admin"],
    "apptio":          ["finance", "it_admin"],
    "gitlab":          ["developer", "l3_support", "it_admin"],
    "puppet":          ["l3_support", "it_admin"],
    "gcp_observability": ["l2_support", "l3_support", "it_admin"],
}

SOURCE_VOLATILITY: dict[str, str] = {
    "zabbix": "dynamic", "dynatrace": "dynamic", "gcp_observability": "dynamic",
    "sentinel_one": "dynamic", "tenable": "dynamic",
    "servicenow": "static", "jira": "static", "confluence": "static",
    "sharepoint": "static", "leanix": "static", "apptio": "static",
    "gitlab": "static", "puppet": "static",
}

DOC_TYPE_MAP: dict[str, str] = {
    "zabbix": "monitoring_metric",
    "dynatrace": "apm_event",
    "servicenow": "incident",
    "jira": "ticket",
    "confluence": "kb_article",
    "sharepoint": "kb_article",
    "leanix": "cmdb",
    "apptio": "financial",
    "gitlab": "config",
    "puppet": "config",
    "tenable": "vulnerability",
    "wiz": "vulnerability",
    "sentinel_one": "security_event",
    "gcp_observability": "monitoring_metric",
}


def canonical_entity_id(name: str) -> str:
    """Stable ID for an entity name, regardless of source system."""
    return hashlib.sha256(name.lower().strip().encode()).hexdigest()[:16]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def normalize_record(
    raw: dict[str, Any],
    source_system: str,
    content_field: str,
    url_field: str = "",
    entity_name_fields: list[str] | None = None,
    timestamp_field: str = "",
    extra_metadata: dict | None = None,
) -> list[Document]:
    """
    Normalize a raw record from any source system into Document chunks.

    Args:
        raw: The raw record dict from source API
        source_system: e.g. "servicenow", "confluence"
        content_field: The field key that holds the main text content
        url_field: Field key for source URL
        entity_name_fields: Field keys for entity names (for entity_refs)
        timestamp_field: Field key for timestamp
        extra_metadata: Any extra k/v to store

    Returns:
        List of Document chunks ready for indexing
    """
    content = str(raw.get(content_field, "")).strip()
    if not content:
        return []

    url = str(raw.get(url_field, "")) if url_field else ""

    entity_refs = []
    for field in (entity_name_fields or []):
        val = raw.get(field)
        if val:
            entity_refs.append(canonical_entity_id(str(val)))

    ts_raw = raw.get(timestamp_field, "") if timestamp_field else ""
    timestamp = str(ts_raw) if ts_raw else datetime.now(timezone.utc).isoformat()

    rbac_tags = SOURCE_RBAC.get(source_system, ["l1_support"])
    volatility = SOURCE_VOLATILITY.get(source_system, "static")
    doc_type = DOC_TYPE_MAP.get(source_system, "unknown")

    metadata = extra_metadata or {}

    chunks = chunk_text(content)
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append(Document(
            id=str(uuid.uuid4()),
            content=chunk,
            source_system=source_system,
            source_url=url,
            doc_type=doc_type,
            timestamp=timestamp,
            rbac_tags=rbac_tags,
            entity_refs=entity_refs,
            volatility=volatility,
            metadata={
                "chunk_index": i,
                "total_chunks": len(chunks),
                **metadata,
            },
        ))
    return docs