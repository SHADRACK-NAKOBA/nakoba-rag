"""
data_plane/ingestion/connectors.py

Source system data ingestion connectors.
Each connector fetches data, normalizes it, and returns Document chunks
ready for indexing into the vector store.
"""
from __future__ import annotations
import base64
import logging
from typing import Any

import httpx

from config.settings import get_settings
from data_plane.normalization.normalizer import normalize_record
from rag.vectorstore.store import Document

logger = logging.getLogger(__name__)
s = get_settings()

TIMEOUT = httpx.Timeout(30.0, connect=5.0)


# ── ServiceNow ────────────────────────────────────────────────────────────────

async def fetch_servicenow_incidents(limit: int = 500) -> list[Document]:
    """Fetch recent ServiceNow incidents for indexing."""
    if not s.servicenow_url:
        logger.warning("ServiceNow not configured — skipping")
        return []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{s.servicenow_url}/api/now/table/incident",
            auth=(s.servicenow_user, s.servicenow_pass),
            params={
                "sysparm_limit": limit,
                "sysparm_fields": "number,short_description,description,state,priority,opened_at,resolved_at,cmdb_ci,assignment_group",
                "sysparm_query": "ORDERBYDESCopened_at",
            },
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])

    docs = []
    for r in records:
        content = (
            f"Incident: {r.get('number','')}\n"
            f"Summary: {r.get('short_description','')}\n"
            f"Description: {r.get('description','')}\n"
            f"State: {r.get('state','')}\n"
            f"Priority: {r.get('priority','')}\n"
            f"CI: {r.get('cmdb_ci','')}\n"
            f"Opened: {r.get('opened_at','')}\n"
            f"Resolved: {r.get('resolved_at','')}"
        )
        docs.extend(normalize_record(
            raw={"content": content, **r},
            source_system="servicenow",
            content_field="content",
            entity_name_fields=["cmdb_ci", "assignment_group"],
            timestamp_field="opened_at",
            extra_metadata={"number": r.get("number", "")},
        ))
    logger.info("ServiceNow: %d incidents → %d chunks", len(records), len(docs))
    return docs


async def fetch_servicenow_cmdb(limit: int = 1000) -> list[Document]:
    """Fetch CMDB configuration items."""
    if not s.servicenow_url:
        return []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{s.servicenow_url}/api/now/table/cmdb_ci",
            auth=(s.servicenow_user, s.servicenow_pass),
            params={
                "sysparm_limit": limit,
                "sysparm_fields": "name,sys_class_name,ip_address,os,environment,owned_by,support_group",
            },
        )
        resp.raise_for_status()
        records = resp.json().get("result", [])

    docs = []
    for r in records:
        content = (
            f"CI Name: {r.get('name','')}\n"
            f"Class: {r.get('sys_class_name','')}\n"
            f"IP: {r.get('ip_address','')}\n"
            f"OS: {r.get('os','')}\n"
            f"Environment: {r.get('environment','')}\n"
            f"Owner: {r.get('owned_by','')}\n"
            f"Support Group: {r.get('support_group','')}"
        )
        docs.extend(normalize_record(
            raw={"content": content, **r},
            source_system="servicenow",
            content_field="content",
            entity_name_fields=["name", "owned_by"],
        ))
    logger.info("ServiceNow CMDB: %d CIs → %d chunks", len(records), len(docs))
    return docs


# ── Jira ──────────────────────────────────────────────────────────────────────

async def fetch_jira_issues(jql: str = "updated >= -90d", limit: int = 500) -> list[Document]:
    if not s.jira_url:
        return []
    token = base64.b64encode(f"{s.jira_email}:{s.jira_token}".encode()).decode()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{s.jira_url}/rest/api/3/search",
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
            json={
                "jql": jql,
                "maxResults": limit,
                "fields": ["summary", "description", "status", "priority", "created", "updated", "labels", "components"],
            },
        )
        resp.raise_for_status()
        issues = resp.json().get("issues", [])

    docs = []
    for issue in issues:
        f = issue.get("fields", {})
        desc = f.get("description") or {}
        desc_text = ""
        if isinstance(desc, dict):
            # Atlassian Document Format
            for block in desc.get("content", []):
                for inline in block.get("content", []):
                    desc_text += inline.get("text", "") + " "
        content = (
            f"Jira {issue.get('key','')}: {f.get('summary','')}\n"
            f"Status: {f.get('status',{}).get('name','')}\n"
            f"Priority: {f.get('priority',{}).get('name','')}\n"
            f"Labels: {', '.join(f.get('labels',[]))}\n"
            f"Description: {desc_text.strip()}"
        )
        docs.extend(normalize_record(
            raw={"content": content},
            source_system="jira",
            content_field="content",
            timestamp_field="",
            extra_metadata={"key": issue.get("key", "")},
        ))
    logger.info("Jira: %d issues → %d chunks", len(issues), len(docs))
    return docs


# ── Confluence ────────────────────────────────────────────────────────────────

async def fetch_confluence_pages(space_key: str = "", limit: int = 200) -> list[Document]:
    if not s.confluence_url:
        return []
    token = base64.b64encode(f"{s.jira_email}:{s.confluence_token}".encode()).decode()
    params = {
        "limit": limit,
        "expand": "body.storage,history",
    }
    if space_key:
        params["spaceKey"] = space_key

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(
            f"{s.confluence_url}/rest/api/content",
            headers={"Authorization": f"Basic {token}"},
            params=params,
        )
        resp.raise_for_status()
        pages = resp.json().get("results", [])

    import re as _re
    docs = []
    for page in pages:
        html = page.get("body", {}).get("storage", {}).get("value", "")
        clean = _re.sub(r"<[^>]+>", " ", html).strip()
        title = page.get("title", "")
        url = f"{s.confluence_url}/pages/{page.get('id','')}"
        docs.extend(normalize_record(
            raw={"content": f"{title}\n\n{clean}", "url": url},
            source_system="confluence",
            content_field="content",
            url_field="url",
        ))
    logger.info("Confluence: %d pages → %d chunks", len(pages), len(docs))
    return docs


# ── Ingestion orchestrator ─────────────────────────────────────────────────────

async def run_full_ingestion() -> int:
    """Run all connectors and index results. Returns total docs ingested."""
    from rag.retrieval.retriever import get_retriever
    retriever = get_retriever()

    all_docs: list[Document] = []
    all_docs.extend(await fetch_servicenow_incidents())
    all_docs.extend(await fetch_servicenow_cmdb())
    all_docs.extend(await fetch_jira_issues())
    all_docs.extend(await fetch_confluence_pages())

    if all_docs:
        retriever.ingest(all_docs)
    logger.info("Full ingestion complete: %d total chunks indexed", len(all_docs))
    return len(all_docs)