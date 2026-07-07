"""
mcp_gateway/registry.py
Central MCP Tool Registry.
Each tool definition carries: handler, description, required_role, requires_hitl, param schema.
Agents discover available tools via /tools/list and call them via /tools/execute.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from mcp_gateway.tools.live_sources import (
    zabbix_get_metrics, dynatrace_get_problems, dynatrace_get_service_metrics,
    servicenow_get_incidents, servicenow_get_cmdb_ci, jira_search,
    confluence_search, gcp_get_metrics, sentinel_get_threats, puppet_get_node_state,
    puppet_run_task, sentinel_isolate_host, leanix_search_applications,
)


@dataclass
class ToolDef:
    name: str
    description: str
    category: str           # observability | cmdb | knowledge | execution | security
    required_role: str      # minimum role needed
    requires_hitl: bool     # pause for human approval before execution
    params: dict            # JSON Schema for parameters
    handler: Callable[..., Awaitable[Any]] = field(repr=False)


TOOL_REGISTRY: dict[str, ToolDef] = {

    # ── Observability ──────────────────────────────────────────
    "zabbix_get_metrics": ToolDef(
        name="zabbix_get_metrics",
        description="Get current CPU, memory, disk and network metrics for a specific host from Zabbix monitoring.",
        category="observability",
        required_role="l1_support",
        requires_hitl=False,
        params={
            "host_name": {"type": "string", "required": True, "description": "Exact Zabbix host name"},
            "metric_filter": {"type": "string", "required": False, "description": "Filter metrics by name substring"},
        },
        handler=lambda p, _u: zabbix_get_metrics(p["host_name"], p.get("metric_filter", "")),
    ),

    "dynatrace_get_problems": ToolDef(
        name="dynatrace_get_problems",
        description="List open problems and alerts from Dynatrace APM.",
        category="observability",
        required_role="l2_support",
        requires_hitl=False,
        params={
            "selector": {"type": "string", "required": False, "default": "status(OPEN)"},
            "limit": {"type": "integer", "required": False, "default": 10},
        },
        handler=lambda p, _u: dynatrace_get_problems(p.get("selector", "status(OPEN)"), p.get("limit", 10)),
    ),

    "dynatrace_get_service_metrics": ToolDef(
        name="dynatrace_get_service_metrics",
        description="Get throughput, response time, error rate and active sessions for a named service from Dynatrace.",
        category="observability",
        required_role="l2_support",
        requires_hitl=False,
        params={
            "service_name": {"type": "string", "required": True},
            "from_time": {"type": "string", "required": False, "default": "now-1h"},
        },
        handler=lambda p, _u: dynatrace_get_service_metrics(p["service_name"], p.get("from_time", "now-1h")),
    ),

    "gcp_get_metrics": ToolDef(
        name="gcp_get_metrics",
        description="Query Google Cloud Monitoring metrics for GCP services.",
        category="observability",
        required_role="l2_support",
        requires_hitl=False,
        params={
            "project": {"type": "string", "required": True},
            "filter_str": {"type": "string", "required": True},
            "minutes": {"type": "integer", "required": False, "default": 60},
        },
        handler=lambda p, _u: gcp_get_metrics(p["project"], p["filter_str"], p.get("minutes", 60)),
    ),

    # ── CMDB / ServiceNow ──────────────────────────────────────
    "servicenow_get_incidents": ToolDef(
        name="servicenow_get_incidents",
        description="Query ServiceNow for incidents matching a filter. Use ServiceNow query syntax (e.g. 'short_descriptionLIKESSO^opened_at>=2025-01-01').",
        category="cmdb",
        required_role="l1_support",
        requires_hitl=False,
        params={
            "query": {"type": "string", "required": False, "default": "active=true"},
            "limit": {"type": "integer", "required": False, "default": 10},
        },
        handler=lambda p, _u: servicenow_get_incidents(p.get("query", "active=true"), p.get("limit", 10)),
    ),

    "servicenow_get_cmdb_ci": ToolDef(
        name="servicenow_get_cmdb_ci",
        description="Look up a Configuration Item (CI) in ServiceNow CMDB by name.",
        category="cmdb",
        required_role="l1_support",
        requires_hitl=False,
        params={"ci_name": {"type": "string", "required": True}},
        handler=lambda p, _u: servicenow_get_cmdb_ci(p["ci_name"]),
    ),

    # ── Project / Knowledge ────────────────────────────────────
    "jira_search": ToolDef(
        name="jira_search",
        description="Search Jira using JQL. Example: 'project = OPS AND labels = SSO AND created >= -365d'",
        category="knowledge",
        required_role="l1_support",
        requires_hitl=False,
        params={
            "jql": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False, "default": 10},
        },
        handler=lambda p, _u: jira_search(p["jql"], p.get("limit", 10)),
    ),

    "confluence_search": ToolDef(
        name="confluence_search",
        description="Search Confluence documentation and knowledge base articles.",
        category="knowledge",
        required_role="l1_support",
        requires_hitl=False,
        params={
            "query": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False, "default": 5},
        },
        handler=lambda p, _u: confluence_search(p["query"], p.get("limit", 5)),
    ),

    "leanix_search_applications": ToolDef(
        name="leanix_search_applications",
        description="Search LeanIX application portfolio",
        category="knowledge",
        required_role="l1_support",
        requires_hitl=False,
        params={"query": {"type": "string", "required": True}},
        handler=lambda p, _u: leanix_search_applications(p["query"]),
    ),

    # ── Security ───────────────────────────────────────────────
    "sentinel_get_threats": ToolDef(
        name="sentinel_get_threats",
        description="Get active security threats and alerts from SentinelOne EDR.",
        category="security",
        required_role="security",
        requires_hitl=False,
        params={"limit": {"type": "integer", "required": False, "default": 10}},
        handler=lambda p, _u: sentinel_get_threats(limit=p.get("limit", 10)),
    ),

    "puppet_get_node_state": ToolDef(
        name="puppet_get_node_state",
        description="Get the current Puppet state and system facts for a node.",
        category="observability",
        required_role="l2_support",
        requires_hitl=False,
        params={"node_name": {"type": "string", "required": True}},
        handler=lambda p, _u: puppet_get_node_state(p["node_name"]),
    ),

    # ── Execution (HITL gated) ─────────────────────────────────
    "puppet_run_task": ToolDef(
        name="puppet_run_task",
        description="Run a pre-approved Puppet task on a target node. REQUIRES HUMAN APPROVAL.",
        category="execution",
        required_role="l3_support",
        requires_hitl=True,
        params={
            "node": {"type": "string", "required": True},
            "task": {"type": "string", "required": True, "description": "Task name e.g. service::restart"},
            "params": {"type": "object", "required": False, "default": {}},
        },
        handler=lambda p, _u: puppet_run_task(p["node"], p["task"], p.get("params", {})),
    ),

    "sentinel_isolate_host": ToolDef(
        name="sentinel_isolate_host",
        description="Network-isolate a host via SentinelOne for containment. REQUIRES HUMAN APPROVAL.",
        category="execution",
        required_role="security_admin",
        requires_hitl=True,
        params={
            "agent_id": {"type": "string", "required": True},
            "reason": {"type": "string", "required": True},
        },
        handler=lambda p, _u: sentinel_isolate_host(p["agent_id"], p["reason"]),
    ),
}