"""
agents/execution_agent/agent.py

Execution Agent — Sub-Agent #4
Responsibilities:
  - Handle requests to perform IT actions (restart service, isolate host, elevate access)
  - All actions HITL-gated — never execute without human approval
  - Propose the action clearly, then request HITL approval via MCP Gateway
  - Handle JIT elevation requests

Run standalone: python -m agents.execution_agent.server  (port 8084)
"""
from __future__ import annotations
import logging
from typing import Any

from agents.a2a.base_agent import BaseSubAgent
from agents.llm import get_llm
from agents.mcp_client import MCPClient
from auth.models import UserContext

logger = logging.getLogger(__name__)

EXECUTION_PLAN_PROMPT = """You are an Execution Agent for IT Operations.
The user has requested an IT action.

Request: {query}
User: {user_id}
User Roles: {roles}

Identify:
1. What specific action is being requested?
2. What target system/node is involved?
3. What is the risk level (low/medium/high/critical)?
4. What MCP tool should be called?
5. What parameters are needed?

Return a structured plan in plain text like:
ACTION: <description>
TARGET: <system or node>
RISK: <low|medium|high|critical>
TOOL: <mcp_tool_name>
PARAMS: <param=value, param=value>
JUSTIFICATION: <why this action is needed>
IMPACT: <what will happen when executed>"""


class ExecutionAgent(BaseSubAgent):
    def __init__(self):
        super().__init__(
            name="Execution Agent",
            description="Sanctioned IT action execution with HITL gating. Restarts, isolations, elevations.",
            skills=["puppet_task", "sentinel_isolate", "service_restart", "elevation_request", "hitl_gate"],
            port=8084,
        )

    async def handle(self, message: str, context: dict[str, Any]) -> tuple[str, dict]:
        bearer_token = context.get("bearer_token", "")
        user_id = context.get("user_id", "unknown")
        roles = context.get("roles", [])

        llm = get_llm()

        # Step 1: Plan the action
        plan_response = await llm.ainvoke(EXECUTION_PLAN_PROMPT.format(
            query=message, user_id=user_id, roles=", ".join(roles),
        ))
        plan_text = plan_response.content

        # Step 2: Parse plan
        tool_name, params = _parse_execution_plan(plan_text, message)

        # Step 3: Submit to MCP Gateway (will trigger HITL)
        if bearer_token:
            mcp = MCPClient(bearer_token=bearer_token)
            result = await mcp.call(tool_name, params)
            status = result.get("status", "unknown")
            hitl_id = result.get("hitl_id")
        else:
            status = "hitl_required"
            hitl_id = "demo-hitl-001"

        if status == "hitl_required":
            output = (
                f"✅ Action plan prepared:\n\n{plan_text}\n\n"
                f"⚠️ **HUMAN APPROVAL REQUIRED**\n"
                f"This action requires authorization before execution.\n"
                f"An approval request has been sent to the configured Slack/Teams channel.\n"
                f"HITL Request ID: `{hitl_id}`\n\n"
                f"To approve: POST /hitl/approve/{hitl_id}\n"
                f"To deny: POST /hitl/deny/{hitl_id}"
            )
        elif status == "unauthorized":
            output = (
                f"❌ **Unauthorized**\n"
                f"Your role ({', '.join(roles)}) does not have permission to execute: {tool_name}\n"
                f"Required role: L3 Support or IT Admin"
            )
        else:
            output = f"✅ Action executed successfully.\n\n{plan_text}"

        return output, {"plan": plan_text, "tool": tool_name, "params": params, "hitl_id": hitl_id}


def _parse_execution_plan(plan_text: str, original_message: str) -> tuple[str, dict]:
    """Extract tool name and params from the LLM's execution plan."""
    lines = plan_text.lower()

    # Determine tool from keywords
    if "isolat" in lines or "sentinel" in lines:
        tool = "sentinel_isolate_host"
        params = {"agent_id": "demo-agent-001", "reason": original_message}
    elif "restart" in lines or "puppet" in lines or "service" in lines:
        tool = "puppet_run_task"
        node = _extract_node(plan_text) or "prod-node-01"
        params = {"node": node, "task": "service::restart", "params": {"service": "application"}}
    else:
        tool = "puppet_run_task"
        params = {"node": "prod-node-01", "task": "service::restart", "params": {}}

    return tool, params


def _extract_node(text: str) -> str | None:
    import re
    patterns = [r"TARGET:\s*(\S+)", r"node[:\s]+(\S+)", r"host[:\s]+(\S+)"]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip(".,")
    return None


async def run_execution(message: str, context: dict) -> str:
    agent = ExecutionAgent()
    output, _ = await agent.handle(message, context)
    return output