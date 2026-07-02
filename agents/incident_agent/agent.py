"""
agents/incident_agent/agent.py

Incident Agent — Sub-Agent #2
Responsibilities:
  - Query ServiceNow for incident records
  - Query Jira for related tickets
  - Query Dynatrace for APM problems
  - Count, summarize and find patterns in incidents
  - Answer questions like "How many SSO outages in the last year?"

Run standalone: python -m agents.incident_agent.server  (port 8082)
"""
from __future__ import annotations
import logging
from typing import Any

from agents.a2a.base_agent import BaseSubAgent
from agents.llm import get_llm
from agents.mcp_client import MCPClient
from rag.retrieval.retriever import get_retriever
from auth.models import UserContext

logger = logging.getLogger(__name__)

INCIDENT_SYNTHESIS_PROMPT = """You are an Incident Analysis Agent for IT Operations.

The user asked: {query}

Data collected from live systems and knowledge base:

ServiceNow Incidents:
{snow_data}

Jira Tickets:
{jira_data}

Dynatrace Problems:
{dynatrace_data}

RAG Knowledge Base Context:
{rag_context}

Provide a precise, quantified answer. Requirements:
- Give exact counts where requested
- List key incidents with ID, date, and summary
- Identify patterns (e.g., most common root cause)
- Cite source for every data point [Source: ServiceNow], [Source: Jira], etc.
- If data is from demo/unavailable system, say so clearly"""


class IncidentAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(
            name="Incident Agent",
            description="Incident analysis: counts, patterns, root causes across ServiceNow, Jira, Dynatrace",
            skills=["servicenow_incidents", "jira_tickets", "dynatrace_problems", "incident_pattern_analysis"],
            port=8082,
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

        # Build ServiceNow query from the message
        # Detect time range and keywords
        snow_query = _build_snow_query(message)
        jira_jql = _build_jira_jql(message)

        # Parallel tool calls
        snow_result = {}
        jira_result = {}
        dt_result = {}

        if mcp:
            import asyncio
            snow_r, jira_r, dt_r = await asyncio.gather(
                mcp.call("servicenow_get_incidents", {"query": snow_query, "limit": 20}),
                mcp.call("jira_search", {"jql": jira_jql, "limit": 20}),
                mcp.call("dynatrace_get_problems", {"selector": "status(OPEN)", "limit": 10}),
            )
            snow_result = snow_r.get("result", {})
            jira_result = jira_r.get("result", {})
            dt_result = dt_r.get("result", {})
        else:
            # No bearer token — use demo data from tool handlers directly
            from mcp_gateway.tools.live_sources import (
                servicenow_get_incidents, jira_search, dynatrace_get_problems
            )
            snow_result = await servicenow_get_incidents(snow_query, 20)
            jira_result = await jira_search(jira_jql, 20)
            dt_result = await dynatrace_get_problems()

        # RAG context
        rag_results = retriever.retrieve(message, user, top_k=4,
                                          source_systems=["servicenow", "jira"])
        rag_context = retriever.format_context(rag_results, message)

        import json
        prompt = INCIDENT_SYNTHESIS_PROMPT.format(
            query=message,
            snow_data=json.dumps(snow_result, indent=2)[:3000],
            jira_data=json.dumps(jira_result, indent=2)[:2000],
            dynatrace_data=json.dumps(dt_result, indent=2)[:1000],
            rag_context=rag_context[:2000],
        )

        response = await llm.ainvoke(prompt)
        return response.content, {
            "snow_records": snow_result,
            "jira_records": jira_result,
            "dynatrace_records": dt_result,
        }


def _build_snow_query(message: str) -> str:
    """Build a ServiceNow sysparm_query from natural language."""
    msg = message.lower()
    parts = ["active=false^ORactive=true"]  # All states
    if "sso" in msg:
        parts.append("short_descriptionLIKESSO^ORdescriptionLIKESSO^ORshort_descriptionLIKElogin^ORshort_descriptionLIKEauthentication")
    if "last year" in msg or "past year" in msg:
        parts.append("opened_at>=javascript:gs.beginningOfLast365Days()")
    elif "last month" in msg:
        parts.append("opened_at>=javascript:gs.beginningOfLastMonth()")
    elif "last week" in msg:
        parts.append("opened_at>=javascript:gs.beginningOfLastWeek()")
    return "^".join(parts)


def _build_jira_jql(message: str) -> str:
    """Build Jira JQL from natural language."""
    msg = message.lower()
    parts = []
    if "sso" in msg:
        parts.append('(text ~ "SSO" OR labels = "SSO" OR text ~ "authentication")')
    if "outage" in msg or "incident" in msg:
        parts.append('(issuetype = Bug OR issuetype = Incident OR labels = "outage")')
    if "last year" in msg:
        parts.append("created >= -365d")
    elif "last month" in msg:
        parts.append("created >= -30d")
    return " AND ".join(parts) if parts else "created >= -365d ORDER BY created DESC"


async def run_incident(message: str, context: dict) -> str:
    agent = IncidentAgent()
    output, _ = await agent.handle(message, context)
    return output
