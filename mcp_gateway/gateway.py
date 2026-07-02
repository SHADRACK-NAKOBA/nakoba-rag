"""
mcp_gateway/gateway.py
MCP Gateway — FastAPI application.

Endpoints:
  POST /tools/execute      — Execute a registered tool (auth + RBAC + HITL + audit)
  GET  /tools/list         — List tools available to the authenticated user
  POST /hitl/approve/{id}  — Approve a pending HITL action
  POST /hitl/deny/{id}     — Deny a pending HITL action
  GET  /hitl/status/{id}   — Check HITL request status
  POST /auth/token         — Issue JWT (dev only — in prod use your IdP)
  GET  /health             — Health check
"""
from __future__ import annotations
import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth.middleware import get_current_user
from auth.models import UserContext, LoginRequest, TokenResponse
from auth.jwt_handler import create_access_token
from auth.rbac import is_tool_authorized
from mcp_gateway.registry import TOOL_REGISTRY
from mcp_gateway.audit import audit_log
from mcp_gateway import hitl as hitl_store

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nakoba MCP Gateway",
    description="Secure execution bridge between Nakoba AI agents and enterprise systems.",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class ToolCallRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = {}
    session_id: str | None = None
    hitl_approval_token: str | None = None   # Pre-approved HITL token


class ToolCallResponse(BaseModel):
    request_id: str
    tool_name: str
    status: str        # success | error | hitl_required | unauthorized
    result: Any | None = None
    error: str | None = None
    hitl_id: str | None = None
    timestamp: str = ""


# ── Auth (dev convenience — replace with real IdP in prod) ───────────────────

# Demo user store — replace with LDAP/IdP lookup
DEMO_USERS = {
    "admin":    {"password": "admin123",   "roles": ["it_admin"]},
    "l3user":   {"password": "l3pass",     "roles": ["l3_support"]},
    "l2user":   {"password": "l2pass",     "roles": ["l2_support"]},
    "l1user":   {"password": "l1pass",     "roles": ["l1_support"]},
    "secuser":  {"password": "secpass",    "roles": ["security"]},
}


@app.post("/auth/token", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Issue a JWT. Dev only — in production, users auth via your corporate IdP."""
    user_data = DEMO_USERS.get(body.username)
    if not user_data or user_data["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(
        user_id=body.username,
        email=f"{body.username}@your-company.com",
        roles=user_data["roles"],
    )
    return TokenResponse(access_token=token)


# ── Tool execution ────────────────────────────────────────────────────────────

@app.post("/tools/execute", response_model=ToolCallResponse)
async def execute_tool(
    body: ToolCallRequest,
    user: UserContext = Depends(get_current_user),
):
    request_id = str(uuid.uuid4())
    ts = datetime.utcnow().isoformat()

    # 1. Tool exists?
    tool = TOOL_REGISTRY.get(body.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{body.tool_name}' not found.")

    # 2. RBAC check
    authorized, reason = is_tool_authorized(body.tool_name, user)
    if not authorized:
        await audit_log(request_id, user.user_id, body.tool_name, "unauthorized", body.parameters)
        raise HTTPException(status_code=403, detail=reason)

    # 3. HITL gate
    if tool.requires_hitl and not body.hitl_approval_token:
        hitl_id = await hitl_store.request_approval(
            request_id=request_id,
            user_id=user.user_id,
            tool_name=body.tool_name,
            parameters=body.parameters,
        )
        await audit_log(request_id, user.user_id, body.tool_name, "hitl_required", body.parameters)
        return ToolCallResponse(
            request_id=request_id, tool_name=body.tool_name,
            status="hitl_required", hitl_id=hitl_id, timestamp=ts,
        )

    # 4. Execute
    try:
        result = await tool.handler(body.parameters, user)
        await audit_log(request_id, user.user_id, body.tool_name, "success",
                        body.parameters, result_summary=str(result)[:500])
        return ToolCallResponse(
            request_id=request_id, tool_name=body.tool_name,
            status="success", result=result, timestamp=ts,
        )
    except Exception as e:
        logger.error("Tool '%s' error: %s", body.tool_name, e)
        await audit_log(request_id, user.user_id, body.tool_name, "error",
                        body.parameters, error=str(e))
        return ToolCallResponse(
            request_id=request_id, tool_name=body.tool_name,
            status="error", error=str(e), timestamp=ts,
        )


@app.get("/tools/list")
async def list_tools(user: UserContext = Depends(get_current_user)):
    from auth.rbac import check_role
    visible = [
        {
            "name": name,
            "description": t.description,
            "category": t.category,
            "requires_hitl": t.requires_hitl,
            "required_role": t.required_role,
            "params": t.params,
        }
        for name, t in TOOL_REGISTRY.items()
        if check_role(user, t.required_role)
    ]
    return {"tools": visible, "count": len(visible), "user_roles": user.roles}


# ── HITL approval endpoints ───────────────────────────────────────────────────

@app.post("/hitl/approve/{hitl_id}")
async def approve_hitl(hitl_id: str, user: UserContext = Depends(get_current_user)):
    record = hitl_store.approve(hitl_id, user.user_id)
    if "error" in record:
        raise HTTPException(status_code=404, detail=record["error"])
    return {"message": "Approved", "hitl_id": hitl_id, "approver": user.user_id}


@app.post("/hitl/deny/{hitl_id}")
async def deny_hitl(hitl_id: str, user: UserContext = Depends(get_current_user)):
    record = hitl_store.deny(hitl_id, user.user_id)
    if "error" in record:
        raise HTTPException(status_code=404, detail=record["error"])
    return {"message": "Denied", "hitl_id": hitl_id, "denier": user.user_id}


@app.get("/hitl/status/{hitl_id}")
async def hitl_status(hitl_id: str, user: UserContext = Depends(get_current_user)):
    record = hitl_store.get_status(hitl_id)
    if not record:
        raise HTTPException(status_code=404, detail="HITL request not found")
    return record


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "nakoba-mcp-gateway",
            "timestamp": datetime.utcnow().isoformat(),
            "tools_registered": len(TOOL_REGISTRY)}