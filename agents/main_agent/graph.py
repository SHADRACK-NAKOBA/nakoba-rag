"""
agents/main_agent/graph.py

Main Orchestrator Agent — LangGraph stateful reasoning graph WITH A2A.

Full reasoning loop from the architecture document:
  Node 1: detect_intent     — classify query, set routing
  Node 2: rag_retrieval     — pull initial context from vector store
  Node 3: a2a_delegate      — delegate to specialized sub-agents via A2A protocol
  Node 4: parallel_tools    — parallel live API calls via MCP Gateway
  Node 5: reflection        — evaluate results, determine if more data needed
  Node 6: synthesis         — final Claude response with citations

A2A Sub-Agents (can run as separate servers OR inline fallback):
  triage_agent   :8081 — intent + entity extraction
  incident_agent :8082 — ServiceNow/Jira/Dynatrace incident analysis
  knowledge_agent:8083 — RAG/Confluence/LeanIX/CMDB knowledge
  execution_agent:8084 — HITL-gated IT action execution
"""
from __future__ import annotations
import json
import logging
from typing import Annotated, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from agents.llm import get_llm
from agents.mcp_client import MCPClient
from agents.a2a.coordinator import A2ACoordinator
from rag.retrieval.retriever import get_retriever
from auth.models import UserContext

logger = logging.getLogger(__name__)

MAX_REFLECT = 2


# ── Graph State ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    user_roles: list[str]
    bearer_token: str
    session_id: str
    # Routing
    intent: str
    sub_intent: str
    entities: list[str]
    # RAG
    rag_context: str
    # A2A results from sub-agents
    a2a_results: dict[str, str]
    # MCP tool results
    tool_results: list[dict]
    # HITL
    requires_hitl: bool
    hitl_ids: list[str]
    # Reflection
    reflection_notes: str
    iteration: int
    # Output
    final_response: str


# ── Prompts ────────────────────────────────────────────────────────────────────

INTENT_PROMPT = """Classify this IT Operations query. Return only JSON, no markdown.

Query: {query}

{{
  "intent": "<observability|incident|knowledge|execution|financial|hybrid>",
  "sub_intent": "<one-sentence description>",
  "entities": ["<names of systems/apps/CIs mentioned>"],
  "needs_incident_agent": <true|false>,
  "needs_knowledge_agent": <true|false>,
  "needs_execution_agent": <true|false>,
  "needs_live_api": <true|false>
}}"""

SYNTHESIS_PROMPT = """You are Nakoba, an expert IT Operations AI assistant.

Original question: {query}

Results from specialized sub-agents:
{a2a_results}

Additional live API data:
{tool_results}

Background knowledge from RAG database:
{rag_context}

Reflection notes: {reflection_notes}

User roles: {user_roles}

Provide a clear, precise, complete answer:
- Cite every data point: [Source: ServiceNow], [Source: Jira], [Source: Confluence], [Source: Dynatrace], etc.
- For counts: give exact numbers
- For architecture: list all components with relationships
- For process/policy: give numbered steps
- For execution requests: show the proposed action and HITL status
- If data is limited/demo: say so, but still give the best answer possible
- Format clearly with sections if answer is complex"""


# ── Nodes ──────────────────────────────────────────────────────────────────────

async def detect_intent(state: AgentState) -> dict:
    """Node 1 — Detect intent and entities from the user query."""
    query = _last_human(state)
    llm = get_llm()
    resp = await llm.ainvoke(INTENT_PROMPT.format(query=query))
    try:
        data = _parse_json(resp.content)
    except Exception:
        data = {"intent": "knowledge", "sub_intent": query,
                "entities": [], "needs_incident_agent": False,
                "needs_knowledge_agent": True, "needs_execution_agent": False,
                "needs_live_api": False}
    logger.info("Intent: %s | entities: %s", data.get("intent"), data.get("entities"))
    return {
        "intent": data.get("intent", "knowledge"),
        "sub_intent": data.get("sub_intent", ""),
        "entities": data.get("entities", []),
        "a2a_results": {},
        "tool_results": [],
        "requires_hitl": False,
        "hitl_ids": [],
        "reflection_notes": "",
        "iteration": 0,
        "_routing": data,  # pass routing flags forward
    }


async def rag_retrieval(state: AgentState) -> dict:
    """Node 2 — Pull initial context from vector store."""
    query = _last_human(state)
    user = _user(state)
    retriever = get_retriever()
    results = retriever.retrieve(query, user, top_k=6)
    ctx = retriever.format_context(results, query)
    logger.info("RAG: retrieved %d chunks", len(results))
    return {"rag_context": ctx}


async def a2a_delegate(state: AgentState) -> dict:
    """
    Node 3 — Delegate to specialized sub-agents via A2A protocol.
    Runs sub-agents in PARALLEL where applicable.
    """
    query = _last_human(state)
    context = {
        "user_id": state["user_id"],
        "roles": state["user_roles"],
        "bearer_token": state["bearer_token"],
        "session_id": state["session_id"],
        "intent": state["intent"],
        "entities": state["entities"],
        "rag_context": state["rag_context"][:1000],  # give sub-agents initial context
    }
    coordinator = A2ACoordinator()
    intent = state["intent"]
    tasks = []

    # Always run triage first (it enriches context for others)
    # For parallel execution: bundle incident + knowledge together when both needed
    if intent in ("incident",):
        tasks = [
            {"agent_name": "incident", "task": query, "context": context},
            {"agent_name": "knowledge", "task": query, "context": context},
        ]
    elif intent in ("knowledge", "financial"):
        tasks = [{"agent_name": "knowledge", "task": query, "context": context}]
    elif intent == "observability":
        # Observability: knowledge agent for CMDB + live tools handle the metrics
        tasks = [{"agent_name": "knowledge", "task": query, "context": context}]
    elif intent == "execution":
        tasks = [{"agent_name": "execution", "task": query, "context": context}]
    elif intent == "hybrid":
        tasks = [
            {"agent_name": "incident", "task": query, "context": context},
            {"agent_name": "knowledge", "task": query, "context": context},
        ]
    else:
        tasks = [{"agent_name": "knowledge", "task": query, "context": context}]

    logger.info("A2A delegating to %d sub-agents in parallel: %s",
                len(tasks), [t["agent_name"] for t in tasks])

    results = await coordinator.delegate_parallel(tasks)

    a2a_results = {}
    requires_hitl = False
    hitl_ids = []
    for r in results:
        a2a_results[r.agent_name] = r.output
        if "HITL Request ID" in r.output or "hitl_required" in r.status:
            requires_hitl = True
            import re
            hitl_match = re.search(r'HITL Request ID[:`\s]+([a-f0-9\-]+)', r.output)
            if hitl_match:
                hitl_ids.append(hitl_match.group(1))

    return {
        "a2a_results": a2a_results,
        "requires_hitl": requires_hitl,
        "hitl_ids": hitl_ids,
    }


async def parallel_live_tools(state: AgentState) -> dict:
    """
    Node 4 — For observability queries, make parallel live API calls via MCP.
    This runs ALONGSIDE the A2A delegation (both happen before synthesis).
    """
    intent = state["intent"]
    query = _last_human(state)
    bearer = state["bearer_token"]
    tool_results = []

    if intent not in ("observability", "hybrid"):
        return {"tool_results": tool_results}

    if not bearer:
        # Demo: call tool handlers directly
        from mcp_gateway.tools.live_sources import dynatrace_get_service_metrics, zabbix_get_metrics
        import asyncio
        entity = (state.get("entities") or ["production"])[0]
        dt_r, zb_r = await asyncio.gather(
            dynatrace_get_service_metrics(entity),
            zabbix_get_metrics(entity),
        )
        mcp = MCPClient("")
        tool_results = [
            {"tool": "dynatrace_get_service_metrics", "formatted": mcp.format_tool_result({"status": "success", "result": dt_r, "tool_name": "dynatrace_get_service_metrics"})},
            {"tool": "zabbix_get_metrics", "formatted": mcp.format_tool_result({"status": "success", "result": zb_r, "tool_name": "zabbix_get_metrics"})},
        ]
    else:
        mcp = MCPClient(bearer_token=bearer)
        entity = (state.get("entities") or ["production"])[0]
        import asyncio
        results = await mcp.call_parallel([
            {"tool_name": "dynatrace_get_service_metrics", "parameters": {"service_name": entity}},
            {"tool_name": "zabbix_get_metrics", "parameters": {"host_name": entity}},
        ])
        tool_results = [{"tool": r["tool_name"], "formatted": mcp.format_tool_result(r)} for r in results]

    logger.info("Parallel tools: %d results", len(tool_results))
    return {"tool_results": tool_results}


async def reflection(state: AgentState) -> dict:
    """Node 5 — Check if we have enough data; optionally fetch more."""
    if state.get("iteration", 0) >= MAX_REFLECT:
        return {"reflection_notes": "Max reflection iterations reached."}

    # If we have A2A results, check if they're substantive
    a2a = state.get("a2a_results", {})
    if not a2a:
        return {"reflection_notes": "No sub-agent results — proceeding with RAG only.", "iteration": 1}

    # Check for errors in sub-agent outputs
    notes = []
    for agent_name, output in a2a.items():
        if "error" in output.lower() or "failed" in output.lower():
            notes.append(f"{agent_name} reported issues")

    return {
        "reflection_notes": "; ".join(notes) if notes else "Sub-agent data collected successfully.",
        "iteration": state.get("iteration", 0) + 1,
    }


async def synthesis(state: AgentState) -> dict:
    """Node 6 — Synthesize everything into a final response."""
    # Special case: HITL required
    if state.get("requires_hitl") and not any(
        "executed successfully" in v for v in state.get("a2a_results", {}).values()
    ):
        hitl_section = state.get("a2a_results", {}).get("Execution Agent", "")
        if hitl_section:
            return {
                "final_response": hitl_section,
                "messages": [AIMessage(content=hitl_section)],
            }

    query = _last_human(state)
    llm = get_llm()

    a2a_text = "\n\n".join(
        f"=== {name} ===\n{output}"
        for name, output in state.get("a2a_results", {}).items()
    ) or "No sub-agent results."

    tool_text = "\n".join(
        r.get("formatted", "") for r in state.get("tool_results", [])
    ) or "No live API data."

    prompt = SYNTHESIS_PROMPT.format(
        query=query,
        a2a_results=a2a_text[:5000],
        tool_results=tool_text[:2000],
        rag_context=state.get("rag_context", "")[:2000],
        reflection_notes=state.get("reflection_notes", ""),
        user_roles=", ".join(state.get("user_roles", [])),
    )

    resp = await llm.ainvoke(prompt)
    return {
        "final_response": resp.content,
        "messages": [AIMessage(content=resp.content)],
    }


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_reflection(state: AgentState) -> Literal["synthesis"]:
    return "synthesis"


# ── Build Graph ────────────────────────────────────────────────────────────────

def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("detect_intent", detect_intent)
    builder.add_node("rag_retrieval", rag_retrieval)
    builder.add_node("a2a_delegate", a2a_delegate)
    builder.add_node("parallel_live_tools", parallel_live_tools)
    builder.add_node("reflection", reflection)
    builder.add_node("synthesis", synthesis)

    builder.add_edge(START, "detect_intent")
    builder.add_edge("detect_intent", "rag_retrieval")
    builder.add_edge("rag_retrieval", "a2a_delegate")
    builder.add_edge("a2a_delegate", "parallel_live_tools")
    builder.add_edge("parallel_live_tools", "reflection")
    builder.add_conditional_edges("reflection", route_after_reflection)
    builder.add_edge("synthesis", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Helpers ────────────────────────────────────────────────────────────────────

def _last_human(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _user(state: AgentState) -> UserContext:
    return UserContext(
        user_id=state["user_id"],
        email=f"{state['user_id']}@company.com",
        roles=state["user_roles"],
        token=state["bearer_token"],
    )


def _parse_json(text: str) -> dict:
    import re
    text = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`").strip()
    return json.loads(text)