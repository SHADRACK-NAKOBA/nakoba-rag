"""auth/rbac.py — RBAC policy engine"""
from fastapi import HTTPException, status
from auth.models import UserContext

# Role hierarchy
ROLE_HIERARCHY = {
    "it_admin":       {"l3_support", "l2_support", "l1_support", "developer", "finance", "security"},
    "l3_support":     {"l2_support", "l1_support"},
    "l2_support":     {"l1_support"},
    "security_admin": {"security"},
    "l1_support":     set(),
    "developer":      set(),
    "finance":        set(),
    "security":       set(),
    "public":         set(),
}


def get_effective_roles(user: UserContext) -> set[str]:
    """Expand roles using hierarchy."""
    effective = set(user.roles)
    for role in list(effective):
        effective |= ROLE_HIERARCHY.get(role, set())
    return effective


def check_role(user: UserContext, required_role: str) -> bool:
    return required_role in get_effective_roles(user) or "public" == required_role


def require_role(required_role: str):
    """FastAPI dependency factory."""
    def _dep(user: UserContext):
        if not check_role(user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required. Your roles: {user.roles}",
            )
        return user
    return _dep


# Tool → minimum required role mapping
TOOL_ROLE_MAP: dict[str, str] = {
    # Read-only observability
    "zabbix_get_metrics":        "l1_support",
    "dynatrace_get_problems":    "l2_support",
    "gcp_get_metrics":           "l1_support",
    "sentinel_get_threats":      "security",
    "tenable_get_vulns":         "security",
    "wiz_get_findings":          "security",
    "puppet_get_state":          "l2_support",
    # CMDB / KB reads
    "servicenow_get_incidents":  "l1_support",
    "servicenow_get_cmdb":       "l1_support",
    "jira_search":               "l1_support",
    "confluence_search":         "l1_support",
    # Execution (HITL gated)
    "puppet_run_task":           "l3_support",
    "sentinel_isolate_host":     "security_admin",
    "vm_restart_service":        "l3_support",
    "vm_provision":              "it_admin",
    "change_firewall":           "it_admin",
}


def is_tool_authorized(tool_name: str, user: UserContext) -> tuple[bool, str]:
    required = TOOL_ROLE_MAP.get(tool_name, "l1_support")
    if check_role(user, required):
        return True, ""
    return False, f"Tool '{tool_name}' requires role '{required}'. User has: {user.roles}"