"""Stable, redacted demo report rendering."""

import json
from dataclasses import asdict
from typing import Any

from cloudsaver.domain import Finding

SCHEMA_VERSION = "1.0.0"


def document(observed_at: str, findings: list[Finding]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "data_kind": "DEMO",
        "notice": "DEMO DATA",
        "scanned_at": observed_at,
        "scope": {"requested": ["demo"], "completed": ["demo"], "failed": []},
        "status": "COMPLETE",
        "findings": [
            {
                "finding_id": finding.finding_id,
                "policy_id": finding.policy_id,
                "status": finding.status,
                "resource": {"type": finding.resource_type, "ref": finding.resource_ref},
                "evidence": [asdict(item) for item in finding.evidence],
                "risk": asdict(finding.risk),
                "savings": asdict(finding.savings),
                "explanation": finding.explanation,
            }
            for finding in findings
        ],
        "collection_issues": [],
    }


def render_json(observed_at: str, findings: list[Finding]) -> str:
    return (
        json.dumps(document(observed_at, findings), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )


def render_table(observed_at: str, findings: list[Finding]) -> str:
    rows = [("FINDING ID", "STATUS", "RISK", "SAVINGS")]
    rows.extend(
        (finding.finding_id, finding.status, finding.risk.level, finding.savings.potential_savings)
        for finding in findings
    )
    widths = [max(len(row[index]) for row in rows) for index in range(4)]
    lines = ["DEMO DATA — CloudSaver", f"Observed at: {observed_at}", ""]
    lines.extend(
        "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip()
        for row in rows
    )
    lines.append("")
    lines.append("Candidates need human review. Savings are UNKNOWN without pricing data.")
    return "\n".join(lines) + "\n"


def inventory_document(inventory: Any) -> dict[str, Any]:
    """Serialize the AWS discovery result through an explicit public allowlist."""
    return {
        "schema_version": SCHEMA_VERSION,
        "data_kind": "AWS",
        "scanned_at": inventory.observed_at,
        "account_ref": "REDACTED" if inventory.account_ref else "UNKNOWN",
        "scope": {
            "requested": inventory.requested,
            "completed": inventory.completed,
            "failed": inventory.failed,
        },
        "status": inventory.status,
        "analysis_status": "NOT_EVALUATED",
        "findings": [],
        "resources": [
            {
                "resource_id": item.resource_id,
                "type": item.type,
                "region": item.region,
                "state": item.state,
                "observed_at": item.observed_at,
                "metrics": {
                    "cpu_average": item.cpu_average,
                    "cpu_samples": item.cpu_samples,
                    "status": item.metrics_status,
                    "period_start": item.period_start,
                    "period_end": item.period_end,
                },
            }
            for item in inventory.resources
        ],
        "collection_issues": [asdict(issue) for issue in inventory.issues],
    }


def render_inventory_json(inventory: Any) -> str:
    return (
        json.dumps(inventory_document(inventory), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )


def render_inventory_table(inventory: Any) -> str:
    lines = [
        f"AWS discovery: {inventory.status}",
        f"Observed at: {inventory.observed_at}",
        "Analysis: NOT_EVALUATED (opportunity policies arrive in Phase 3)",
        "",
        "REGION  TYPE  RESOURCE ID  STATE  CPU METRICS",
    ]
    lines.extend(
        f"{item.region}  {item.type}  {item.resource_id}  {item.state}  {item.metrics_status}"
        for item in inventory.resources
    )
    lines.append("")
    lines.append(
        f"Completed scopes: {len(inventory.completed)}; failed scopes: {len(inventory.failed)}"
    )
    lines.extend(
        f"Issue: {issue.scope} {issue.operation} {issue.category}" for issue in inventory.issues
    )
    return "\n".join(lines) + "\n"
