"""
agents/mcp_client.py
HTTP client that agents use to call the MCP Gateway.
All tool calls go through this — never call source systems directly from agents.
"""
from __future__ import annotations
import logging
from typing import Any

import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()


class MCPClient:
    """Thin async client for the MCP Gateway."""

    def __init__(self, bearer_token: str):
        self._token = bearer_token
        self._base = s.mcp_gateway_url
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

    async def call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        session_id: str | None = None,
        hitl_token: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool via the MCP Gateway."""
        payload = {
            "tool_name": tool_name,
            "parameters": parameters,
            "session_id": session_id,
            "hitl_approval_token": hitl_token,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self._base}/tools/execute",
                    headers=self._headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            logger.error("Cannot connect to MCP Gateway at %s", self._base)
            return {"status": "error", "error": f"MCP Gateway unreachable at {self._base}",
                    "tool_name": tool_name}
        except Exception as e:
            logger.error("MCP call failed for %s: %s", tool_name, e)
            return {"status": "error", "error": str(e), "tool_name": tool_name}

    async def call_parallel(self, calls: list[dict]) -> list[dict]:
        """Execute multiple tool calls in parallel."""
        import asyncio
        return await asyncio.gather(*[
            self.call(c["tool_name"], c["parameters"], c.get("session_id"))
            for c in calls
        ])

    def format_tool_result(self, response: dict) -> str:
        """Format MCP response for inclusion in LLM context."""
        tool = response.get("tool_name", "unknown")
        status = response.get("status", "unknown")
        if status == "success":
            import json
            result = response.get("result", {})
            return f"[TOOL:{tool}] {json.dumps(result, indent=2)}"
        elif status == "hitl_required":
            return f"[TOOL:{tool}] ⚠️ Human approval required. HITL ID: {response.get('hitl_id')}"
        elif status == "unauthorized":
            return f"[TOOL:{tool}] ❌ Unauthorized: insufficient permissions"
        else:
            return f"[TOOL:{tool}] ❌ Error: {response.get('error', 'unknown error')}"