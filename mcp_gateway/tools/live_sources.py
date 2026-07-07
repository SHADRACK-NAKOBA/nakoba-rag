"""
mcp_gateway/tools/live_sources.py

Live source tool handlers.
Each function is called by the MCP Gateway when an agent requests a tool.
These are READ-ONLY live API calls — NOT indexed in the vector store
(data is too volatile to cache meaningfully).
"""
from __future__ import annotations
import base64
import logging
from typing import Any

import httpx
from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()
T = httpx.Timeout(20.0, connect=5.0)


async def zabbix_get_metrics(host_name: str, metric_filter: str = "") -> dict:
    """Fetch current performance metrics for a host from Zabbix."""
    if not s.zabbix_url:
        return {"error": "Zabbix not configured", "demo": _demo_metrics(host_name)}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.post(
            f"{s.zabbix_url}/api_jsonrpc.php",
            json={
                "jsonrpc": "2.0", "method": "item.get",
                "params": {
                    "output": ["name", "lastvalue", "units", "lastclock"],
                    "host": host_name,
                    "search": {"name": metric_filter} if metric_filter else {},
                    "sortfield": "name", "limit": 30,
                },
                "auth": s.zabbix_token, "id": 1,
            },
        )
        resp.raise_for_status()
        return {"host": host_name, "metrics": resp.json().get("result", [])}


def _demo_metrics(host: str) -> list[dict]:
    return [
        {"name": "CPU utilization", "lastvalue": "23.4", "units": "%"},
        {"name": "Memory utilization", "lastvalue": "68.1", "units": "%"},
        {"name": "Disk read rate", "lastvalue": "12.3", "units": "MB/s"},
    ]


async def dynatrace_get_problems(selector: str = "status(OPEN)", limit: int = 10) -> dict:
    """Retrieve open problems from Dynatrace APM."""
    if not s.dynatrace_url:
        return {"demo": True, "totalCount": 2, "problems": [
            {"problemId": "P-DEMO1", "title": "High error rate on checkout-service", "status": "OPEN", "severityLevel": "PERFORMANCE"},
            {"problemId": "P-DEMO2", "title": "Response time degradation on API gateway", "status": "OPEN", "severityLevel": "PERFORMANCE"},
        ]}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.dynatrace_url}/api/v2/problems",
            headers={"Authorization": f"Api-Token {s.dynatrace_token}"},
            params={"problemSelector": selector, "pageSize": limit},
        )
        resp.raise_for_status()
        return resp.json()


async def dynatrace_get_service_metrics(service_name: str, from_time: str = "now-1h") -> dict:
    """Get service-level metrics (throughput, response time, error rate)."""
    if not s.dynatrace_url:
        return {"demo": True, "service": service_name, "metrics": {
            "throughput_rpm": 1240, "response_time_ms": 87, "error_rate_pct": 0.3,
            "active_sessions": 342,
        }}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.dynatrace_url}/api/v2/metrics/query",
            headers={"Authorization": f"Api-Token {s.dynatrace_token}"},
            params={
                "metricSelector": "builtin:service.requestCount.total,builtin:service.response.time,builtin:service.errors.total.rate",
                "resolution": "1m", "from": from_time,
                "entitySelector": f'type("SERVICE"),entityName("{service_name}")',
            },
        )
        resp.raise_for_status()
        return resp.json()


async def servicenow_get_incidents(
    query: str = "active=true",
    limit: int = 10,
) -> dict:
    """Query live ServiceNow incidents."""
    if not s.servicenow_url:
        return {"demo": True, "result": [
            {"number": "INC0012345", "short_description": "SSO login failures affecting users in Corp Apps", "state": "2", "priority": "1", "opened_at": "2026-01-15 09:00:00"},
            {"number": "INC0012310", "short_description": "Network latency spike in Production GCP", "state": "6", "priority": "2", "opened_at": "2026-01-10 14:30:00"},
        ]}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.servicenow_url}/api/now/table/incident",
            auth=(s.servicenow_user, s.servicenow_pass),
            params={
                "sysparm_query": query,
                "sysparm_limit": limit,
                "sysparm_fields": "number,short_description,state,priority,opened_at,resolved_at,cmdb_ci,assignment_group,close_notes",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def servicenow_get_cmdb_ci(ci_name: str) -> dict:
    """Look up a Configuration Item in ServiceNow CMDB."""
    if not s.servicenow_url:
        return {"demo": True, "result": [
            {"name": ci_name, "sys_class_name": "cmdb_ci_app_server", "environment": "Production",
             "ip_address": "10.20.30.40", "os": "RHEL 8.6", "support_group": "Platform Engineering"},
        ]}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.servicenow_url}/api/now/table/cmdb_ci",
            auth=(s.servicenow_user, s.servicenow_pass),
            params={"sysparm_query": f"nameLIKE{ci_name}", "sysparm_limit": 5},
        )
        resp.raise_for_status()
        return resp.json()


async def jira_search(jql: str, limit: int = 10) -> dict:
    """Search Jira with JQL."""
    if not s.jira_url:
        return {"demo": True, "total": 1, "issues": [
            {"key": "OPS-4521", "fields": {"summary": f"Query: {jql}", "status": {"name": "In Progress"}, "priority": {"name": "High"}}},
        ]}
    token = base64.b64encode(f"{s.jira_email}:{s.jira_token}".encode()).decode()
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.post(
            f"{s.jira_url}/rest/api/3/search",
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
            json={"jql": jql, "maxResults": limit, "fields": ["summary", "status", "priority", "created", "updated", "labels"]},
        )
        resp.raise_for_status()
        return resp.json()


def _demo_confluence(query: str) -> list[dict]:
    return [
        {"title": f"Process: {query}", "url": "https://confluence.example.com/page/123",
         "excerpt": f"This article covers the process for {query} in detail..."},
    ]


async def confluence_search(query: str, limit: int = 5) -> dict:
    """Search Confluence documentation."""
    if not s.confluence_url:
        return {"demo": True, "results": _demo_confluence(query)}
    try:
        async with httpx.AsyncClient(timeout=T) as c:
            resp = await c.get(
                f"{s.confluence_url}/rest/api/content/search",
                headers={"Authorization": f"Bearer {s.confluence_token}"},
                params={"cql": f'text~"{query}"', "limit": limit, "expand": "excerpt"},
            )
            resp.raise_for_status()
            data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": f"{s.confluence_url}{item.get('_links', {}).get('webui', '')}",
                "excerpt": item.get("excerpt", ""),
            }
            for item in data.get("results", [])
        ]
        return {"results": results}
    except httpx.HTTPError as e:
        logger.warning("Confluence search failed: %s — falling back to demo data", e)
        return {"demo": True, "note": f"Live Confluence unavailable ({e}); showing demo data.",
                "results": _demo_confluence(query)}


async def gcp_get_metrics(project: str, filter_str: str, minutes: int = 60) -> dict:
    """Query GCP Cloud Monitoring metrics."""
    return {"demo": True, "project": project, "filter": filter_str,
            "note": "Connect google-cloud-monitoring SDK for production",
            "sample_data": [{"metric": "kubernetes.io/container/cpu/request_utilization", "value": 0.34}]}


async def sentinel_get_threats(scope: str = "all", limit: int = 10) -> dict:
    """Get active threats from SentinelOne."""
    if not s.sentinel_one_url:
        return {"demo": True, "threats": [
            {"id": "T001", "threatName": "Malicious.Document.Gen", "confidenceLevel": "malicious",
             "agentComputerName": "WORKSTATION-042", "createdAt": "2026-06-25T10:00:00Z"},
        ]}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.sentinel_one_url}/web/api/v2.1/threats",
            headers={"Authorization": f"ApiToken {s.sentinel_one_token}"},
            params={"limit": limit, "resolved": "false"},
        )
        resp.raise_for_status()
        return resp.json()


async def puppet_get_node_state(node_name: str) -> dict:
    """Get Puppet node state and facts."""
    if not s.puppet_url:
        return {"demo": True, "node": node_name, "state": "unchanged",
                "facts": {"os": "RHEL 8.6", "memory_mb": 16384, "cpu_count": 8, "puppet_version": "7.28.0"}}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.get(
            f"{s.puppet_url}/puppet-db/v4/nodes/{node_name}",
            headers={"X-Authentication": s.puppet_token},
        )
        resp.raise_for_status()
        return resp.json()


# ── EXECUTION TOOLS (HITL gated) ─────────────────────────────────────────────

async def puppet_run_task(node: str, task: str, params: dict) -> dict:
    """Run a Puppet task on a node (HITL gated)."""
    if not s.puppet_url:
        return {"demo": True, "job_id": "job-demo-001", "node": node, "task": task,
                "status": "running", "message": "[DEMO] Task dispatched successfully"}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.post(
            f"{s.puppet_url}/orchestrator/v1/command/task",
            headers={"X-Authentication": s.puppet_token, "Content-Type": "application/json"},
            json={"task": task, "params": params, "scope": {"nodes": [node]}},
        )
        resp.raise_for_status()
        return resp.json()


async def sentinel_isolate_host(agent_id: str, reason: str) -> dict:
    """Isolate a host via SentinelOne EDR (HITL gated)."""
    if not s.sentinel_one_url:
        return {"demo": True, "agentId": agent_id, "action": "isolate",
                "status": "success", "message": "[DEMO] Host isolation initiated"}
    async with httpx.AsyncClient(timeout=T) as c:
        resp = await c.post(
            f"{s.sentinel_one_url}/web/api/v2.1/agents/actions/disconnect",
            headers={"Authorization": f"ApiToken {s.sentinel_one_token}", "Content-Type": "application/json"},
            json={"filter": {"ids": [agent_id]}},
        )
        resp.raise_for_status()
        return {"status": "success", "response": resp.json()}