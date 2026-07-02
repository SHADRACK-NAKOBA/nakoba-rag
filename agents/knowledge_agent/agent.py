"""
agents/knowledge_agent/agent.py

Knowledge Agent — Sub-Agent #3
Responsibilities:
  - Answer policy, process, and documentation questions
  - Query CMDB for CI relationships and application dependencies
  - Search Confluence and LeanIX
  - Answer questions like "What CRM systems exist?", "How do I submit a vuln exception?"

Run standalone: python -m agents.knowledge_agent.server  (port 8083)
"""
from __future__ import annotations
import json
import logging
from typing import Any

from agents.a2a.base_agent import BaseSubAgent
from agents.llm import get_llm
from agents.mcp_client import MCPClient
from rag.retrieval.retriever import get_retriever
from auth.models import UserContext

logger = logging.getLogger(__name__)

KNOWLEDGE_SYNTHESIS_PROMPT = """You are a Knowledge Agent for IT Operations.
You specialize in enterprise documentation, CMDB data, and application architecture.

The user asked: {query}

Knowledge Base (RAG) Results:
{rag_context}

Live System Data:
{live_data}

Provide a clear, complete answer. Requirements:
- For architecture questions: list all relevant systems/apps with their relationships
- For process questions: give step-by-step instructions
- For CMDB questions: include environment, owner, dependencies
- Cite every fact with [Source: system_name]
- If something is not in the knowledge base, say so explicitly"""


class KnowledgeAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(
            name="Knowledge Agent",
            description="Enterprise KB search: CMDB, Confluence, LeanIX, architecture, policy questions",
            skills=["rag_hybrid_search", "confluence_search", "leanix_lookup", "cmdb_query", "policy_lookup"],
            port=8083,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> tuple[str, dict]:
        bearer_token = context.get("bearer_token", "")
        user = UserContext(
            user_id=context.get("user_id", "system"),
            email="",
            roles=context.get("roles", ["l1_support"]),
            token=bearer_token,
        )

        mcp = MCPClient(bearer_token=bearer_token) if bearer_token else None
        retriever = get_retriever()
        llm = get_llm()

        # Broad RAG search across KB sources
        rag_results = retriever.retrieve(
            message, user, top_k=8,
            source_systems=["confluence", "leanix", "servicenow", "sharepoint", "puppet"],
        )
        rag_context = retriever.format_context(rag_results, message)

        # Live system calls
        live_data = {}
        if mcp:
            # Parallel: search Confluence + ServiceNow CMDB
            import asyncio
            conf_r, snow_r = await asyncio.gather(
                mcp.call("confluence_search", {"query": message, "limit": 3}),
                mcp.call("servicenow_get_cmdb_ci", {"ci_name": _extract_ci_name(message)}),
            )
            live_data["confluence"] = conf_r.get("result", {})
            live_data["servicenow_cmdb"] = snow_r.get("result", {})
        else:
            from mcp_gateway.tools.live_sources import confluence_search, servicenow_get_cmdb_ci
            live_data["confluence"] = await confluence_search(message, 3)
            live_data["servicenow_cmdb"] = await servicenow_get_cmdb_ci(_extract_ci_name(message))

        prompt = KNOWLEDGE_SYNTHESIS_PROMPT.format(
            query=message,
            rag_context=rag_context[:4000],
            live_data=json.dumps(live_data, indent=2)[:2000],
        )
        response = await llm.ainvoke(prompt)
        return response.content, {"rag_chunks": len(rag_results), "live_data": live_data}


def _extract_ci_name(message: str) -> str:
    """Best-effort extract a CI/system name from the query."""
    import re
    # Look for quoted names
    quoted = re.findall(r'"([^"]+)"', message)
    if quoted:
        return quoted[0]
    # Common IT terms to skip
    skip = {"what", "how", "many", "the", "are", "is", "do", "does", "currently", "systems",
            "exist", "applications", "serve", "which", "enterprise", "crm", "for", "to"}
    words = [w for w in message.lower().split() if len(w) > 3 and w not in skip]
    return words[0] if words else "production"


async def run_knowledge(message: str, context: dict) -> str:
    agent = KnowledgeAgent()
    output, _ = await agent.handle(message, context)
    return output