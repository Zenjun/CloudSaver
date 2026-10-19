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
