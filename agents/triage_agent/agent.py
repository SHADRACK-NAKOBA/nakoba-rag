"""
agents/triage_agent/agent.py

Triage Agent — Sub-Agent #1
Responsibilities:
  - Classify intent of the incoming query
  - Extract entities (CI names, time ranges, system names)
  - Do initial RAG retrieval to ground the response
  - Return structured context for the other sub-agents

Run standalone: python -m agents.triage_agent.server  (port 8081)
"""
from __future__ import annotations
import json
import logging
from typing import Any

from agents.a2a.base_agent import BaseSubAgent
from agents.llm import get_llm
from rag.retrieval.retriever import get_retriever
from auth.models import UserContext

logger = logging.getLogger(__name__)

TRIAGE_PROMPT = """You are a Triage Agent for an IT Operations AI system.
Analyze this query and extract structured information.

Query: {query}

Return ONLY valid JSON (no markdown):
{{
  "intent": "<observability|incident|knowledge|execution|financial|hybrid>",
  "sub_intent": "<specific 1-sentence description>",
  "entities": ["<CI names, system names, app names mentioned>"],
  "time_range": "<e.g. last year, last 1 hour, or null>",
  "requires_live_api": <true|false>,
  "requires_rag": <true|false>,
  "priority_sources": ["<servicenow|jira|dynatrace|zabbix|confluence|leanix|puppet>"],
  "confidence": <0.0-1.0>
}}"""


class TriageAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(
            name="Triage Agent",
            description="Intent classification, entity extraction, and initial RAG retrieval",
            skills=["intent_detection", "rag_search", "ci_lookup", "entity_extraction"],
            port=8081,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> tuple[str, dict]:
        llm = get_llm()
        retriever = get_retriever()
        user = UserContext(
            user_id=context.get("user_id", "system"),
            email="",
            roles=context.get("roles", ["l1_support"]),
        )

        # 1. Classify intent
        response = await llm.ainvoke(TRIAGE_PROMPT.format(query=message))
        try:
            classification = json.loads(response.content)
        except Exception:
            classification = {"intent": "knowledge", "entities": [], "requires_rag": True}

        # 2. RAG retrieval for initial grounding
        rag_results = retriever.retrieve(message, user, top_k=4)
        rag_context = retriever.format_context(rag_results, message)

        output = (
            f"Triage complete.\n"
            f"Intent: {classification.get('intent')}\n"
            f"Sub-intent: {classification.get('sub_intent')}\n"
            f"Entities found: {', '.join(classification.get('entities', [])) or 'none'}\n"
            f"Time range: {classification.get('time_range') or 'not specified'}\n"
            f"Priority sources: {', '.join(classification.get('priority_sources', []))}\n\n"
            f"Initial RAG context:\n{rag_context}"
        )

        return output, {
            "classification": classification,
            "rag_context": rag_context,
            "rag_chunk_count": len(rag_results),
        }


# ── Inline function (used when agent not running as separate server) ───────────

async def run_triage(message: str, context: dict) -> str:
    agent = TriageAgent()
    output, _ = await agent.handle(message, context)
    return output