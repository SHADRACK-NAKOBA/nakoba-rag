"""
agents/a2a/coordinator.py

A2A (Agent-to-Agent) Protocol Coordinator.
The Main Orchestrator uses this to delegate tasks to specialized sub-agents.

Google A2A spec: https://google.github.io/A2A/
Each sub-agent:
  - Serves GET /.well-known/agent.json  (AgentCard)
  - Accepts POST /tasks/send            (receive task)
  - Returns structured result JSON

In local dev, sub-agents run on separate ports:
  triage_agent   → :8081
  incident_agent → :8082
  knowledge_agent→ :8083
  execution_agent→ :8084
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()


# ── A2A Data Models ───────────────────────────────────────────────────────────

@dataclass
class AgentCard:
    """Describes what a sub-agent can do. Served at /.well-known/agent.json"""
    name: str
    url: str
    description: str
    version: str = "1.0"
    skills: list[str] = field(default_factory=list)
    input_modes: list[str] = field(default_factory=lambda: ["text"])
    output_modes: list[str] = field(default_factory=lambda: ["text"])


@dataclass
class A2ATask:
    """Task sent from orchestrator to a sub-agent."""
    id: str
    message: str                    # The natural language sub-task
    context: dict[str, Any]        # user_id, roles, session_id, parent_intent
    session_id: str = ""


@dataclass
class A2AResult:
    """Result returned by a sub-agent."""
    task_id: str
    agent_name: str
    status: str                    # completed | failed | input_required
    output: str                    # The agent's answer text
    data: dict = field(default_factory=dict)   # Structured data if any
    error: str = ""


# ── Local agent registry (ports for local dev) ────────────────────────────────

AGENT_REGISTRY: dict[str, AgentCard] = {
    "triage": AgentCard(
        name="Triage Agent",
        url="http://localhost:8081",
        description="Intent classification, initial RAG context retrieval, CI identification",
        skills=["intent_detection", "rag_search", "ci_lookup", "entity_extraction"],
    ),
    "incident": AgentCard(
        name="Incident Agent",
        url="http://localhost:8082",
        description="Incident analysis across ServiceNow, Jira, Dynatrace. Counts outages, finds root causes.",
        skills=["servicenow_incidents", "jira_tickets", "dynatrace_problems", "pattern_analysis"],
    ),
    "knowledge": AgentCard(
        name="Knowledge Agent",
        url="http://localhost:8083",
        description="Enterprise knowledge base search via Advanced RAG. Answers policy, CMDB, architecture questions.",
        skills=["rag_hybrid_search", "confluence_search", "leanix_lookup", "cmdb_query"],
    ),
    "execution": AgentCard(
        name="Execution Agent",
        url="http://localhost:8084",
        description="Sanctioned IT action execution. All actions HITL-gated.",
        skills=["puppet_task", "sentinel_isolate", "service_restart", "elevation_request"],
    ),
}


# ── A2A Coordinator ───────────────────────────────────────────────────────────

class A2ACoordinator:
    """
    Used by the main orchestrator to delegate to sub-agents.
    Implements the Google A2A task delegation protocol.
    """

    def __init__(self):
        self._timeout = httpx.Timeout(45.0, connect=3.0)

    async def get_agent_card(self, agent_name: str) -> AgentCard:
        """Fetch live AgentCard from sub-agent (falls back to local registry)."""
        card = AGENT_REGISTRY.get(agent_name)
        if not card:
            raise ValueError(f"Unknown agent: {agent_name}")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as c:
                r = await c.get(f"{card.url}/.well-known/agent.json")
                if r.status_code == 200:
                    data = r.json()
                    return AgentCard(**{k: v for k, v in data.items()
                                       if k in AgentCard.__dataclass_fields__})
        except Exception:
            pass  # Use local registry as fallback
        return card

    async def delegate(
        self,
        agent_name: str,
        task: str,
        context: dict[str, Any],
        session_id: str = "",
    ) -> A2AResult:
        """Send a task to one sub-agent and wait for the result."""
        card = AGENT_REGISTRY.get(agent_name)
        if not card:
            return A2AResult(
                task_id="n/a", agent_name=agent_name,
                status="failed", output="",
                error=f"Agent '{agent_name}' not in registry",
            )

        task_id = str(uuid.uuid4())
        payload = {
            "id": task_id,
            "message": task,
            "context": context,
            "session_id": session_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                logger.info("A2A → %s | task_id=%s | task=%s", agent_name, task_id, task[:80])
                r = await c.post(f"{card.url}/tasks/send", json=payload)
                r.raise_for_status()
                data = r.json()
                return A2AResult(
                    task_id=task_id,
                    agent_name=agent_name,
                    status=data.get("status", "completed"),
                    output=data.get("output", ""),
                    data=data.get("data", {}),
                )
        except httpx.ConnectError:
            logger.warning("Sub-agent '%s' not running at %s — using inline fallback", agent_name, card.url)
            return await self._inline_fallback(agent_name, task, context)
        except Exception as e:
            logger.error("A2A error for %s: %s", agent_name, e)
            return A2AResult(
                task_id=task_id, agent_name=agent_name,
                status="failed", output="", error=str(e),
            )

    async def delegate_parallel(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[A2AResult]:
        """
        Delegate multiple tasks to different agents simultaneously.
        tasks = [{"agent_name": "...", "task": "...", "context": {...}}, ...]
        """
        coros = [
            self.delegate(
                agent_name=t["agent_name"],
                task=t["task"],
                context=t.get("context", {}),
                session_id=t.get("session_id", ""),
            )
            for t in tasks
        ]
        return await asyncio.gather(*coros, return_exceptions=False)

    async def _inline_fallback(
        self, agent_name: str, task: str, context: dict
    ) -> A2AResult:
        """
        When a sub-agent is not running (local dev single-process mode),
        execute the agent logic inline within this process.
        This allows the full system to work even without running 4 separate servers.
        """
        try:
            if agent_name == "triage":
                from agents.triage_agent.agent import run_triage
                output = await run_triage(task, context)
            elif agent_name == "incident":
                from agents.incident_agent.agent import run_incident
                output = await run_incident(task, context)
            elif agent_name == "knowledge":
                from agents.knowledge_agent.agent import run_knowledge
                output = await run_knowledge(task, context)
            elif agent_name == "execution":
                from agents.execution_agent.agent import run_execution
                output = await run_execution(task, context)
            else:
                output = f"No fallback for agent: {agent_name}"
            return A2AResult(
                task_id=str(uuid.uuid4()), agent_name=agent_name,
                status="completed", output=output,
            )
        except Exception as e:
            return A2AResult(
                task_id=str(uuid.uuid4()), agent_name=agent_name,
                status="failed", output="", error=str(e),
            )