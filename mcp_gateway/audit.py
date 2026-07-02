"""mcp_gateway/audit.py — Audit logging to BigQuery (or local file in dev)"""
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings

logger = logging.getLogger(__name__)
s = get_settings()


async def audit_log(
    request_id: str,
    user_id: str,
    tool_name: str,
    status: str,
    parameters: dict[str, Any],
    result_summary: str = "",
    error: str = "",
) -> None:
    record = {
        "request_id": request_id,
        "user_id": user_id,
        "tool_name": tool_name,
        "status": status,
        "parameters_json": json.dumps(parameters),
        "result_summary": result_summary[:500],
        "error": error[:500],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if s.app_env == "development":
        # Write to local JSONL file for dev
        log_dir = Path("./data/audit")
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "gateway_events.jsonl", "a") as f:
            f.write(json.dumps(record) + "\n")
        logger.debug("AUDIT: %s", record)
        return

    # Production: BigQuery
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=s.gcp_project_id)
        table = f"{s.gcp_project_id}.{s.bq_dataset}.{s.bq_audit_table}"
        errors = client.insert_rows_json(table, [record])
        if errors:
            logger.error("BigQuery audit errors: %s", errors)
    except Exception as e:
        logger.error("Audit log failed (non-blocking): %s", e)