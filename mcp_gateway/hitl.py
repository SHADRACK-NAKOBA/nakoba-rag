"""
mcp_gateway/hitl.py — Human-in-the-Loop gate.
Stores pending approvals in memory (dev) or Redis (prod).
Sends Slack notification with approve/deny instructions.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()

# In-memory store for dev (use Redis in prod)
_pending: dict[str, dict] = {}


async def request_approval(
    request_id: str,
    user_id: str,
    tool_name: str,
    parameters: dict[str, Any],
) -> str:
    hitl_id = str(uuid.uuid4())
    record = {
        "hitl_id": hitl_id,
        "request_id": request_id,
        "user_id": user_id,
        "tool_name": tool_name,
        "parameters": parameters,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _pending[hitl_id] = record

    await _notify_slack(hitl_id, user_id, tool_name, parameters)
    logger.info("HITL approval requested: hitl_id=%s tool=%s user=%s", hitl_id, tool_name, user_id)
    return hitl_id


async def _notify_slack(hitl_id: str, user_id: str, tool_name: str, params: dict) -> None:
    if not s.hitl_slack_webhook:
        logger.info("HITL [NO WEBHOOK] — would send Slack notification for %s", hitl_id)
        return
    param_text = "\n".join(f"  • *{k}*: `{v}`" for k, v in params.items())
    payload = {"text": (
        f"🔐 *Nakoba HITL Approval Required*\n"
        f"*HITL ID:* `{hitl_id}`\n"
        f"*Requested by:* `{user_id}`\n"
        f"*Tool:* `{tool_name}`\n"
        f"*Parameters:*\n{param_text}\n\n"
        f"To approve: `POST /hitl/approve/{hitl_id}` with your bearer token\n"
        f"To deny:    `POST /hitl/deny/{hitl_id}` with your bearer token"
    )}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(s.hitl_slack_webhook, json=payload)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)


def approve(hitl_id: str, approver_id: str) -> dict:
    if hitl_id not in _pending:
        return {"error": "HITL request not found"}
    _pending[hitl_id]["status"] = "approved"
    _pending[hitl_id]["approver"] = approver_id
    _pending[hitl_id]["decided_at"] = datetime.now(timezone.utc).isoformat()
    return _pending[hitl_id]


def deny(hitl_id: str, approver_id: str) -> dict:
    if hitl_id not in _pending:
        return {"error": "HITL request not found"}
    _pending[hitl_id]["status"] = "denied"
    _pending[hitl_id]["approver"] = approver_id
    _pending[hitl_id]["decided_at"] = datetime.now(timezone.utc).isoformat()
    return _pending[hitl_id]


def get_status(hitl_id: str) -> dict | None:
    return _pending.get(hitl_id)