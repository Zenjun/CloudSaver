"""Stable, redacted demo and AWS report rendering."""

import json
from dataclasses import asdict
from typing import Any

from cloudsaver.domain import Finding

SCHEMA_VERSION = "1.1.0"


def _findings(findings: list[Finding]) -> list[dict[str, Any]]:
    return [
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
    ]


def document(observed_at: str, findings: list[Finding]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "data_kind": "DEMO",
        "notice": "DEMO DATA",
        "scanned_at": observed_at,
        "scope": {"requested": ["demo"], "completed": ["demo"], "failed": []},
        "status": "COMPLETE",
        "findings": _findings(findings),
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


def inventory_document(inventory: Any, findings: list[Finding] | None = None) -> dict[str, Any]:
    """Serialize the AWS discovery result through an explicit public allowlist."""
    analysis_status = "NOT_EVALUATED"
    if findings is not None and inventory.status != "FAILED":
        analysis_status = "COMPLETE" if inventory.status == "COMPLETE" else "PARTIAL"
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
        "analysis_status": analysis_status,
        "findings": _findings(findings or []),
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


def render_inventory_json(inventory: Any, findings: list[Finding] | None = None) -> str:
    return (
        json.dumps(
            inventory_document(inventory, findings), ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n"
    )


def render_inventory_table(inventory: Any, findings: list[Finding] | None = None) -> str:
    analysis_status = inventory_document(inventory, findings)["analysis_status"]
    lines = [
        f"AWS discovery: {inventory.status}",
        f"Observed at: {inventory.observed_at}",
        f"Analysis: {analysis_status}",
        "",
        "REGION  TYPE  RESOURCE ID  STATE  CPU METRICS",
    ]
    lines.extend(
        f"{item.region}  {item.type}  {item.resource_id}  {item.state}  {item.metrics_status}"
        for item in inventory.resources
    )
    lines.append("")
    lines.append("FINDING ID  STATUS  RISK  SAVINGS")
    lines.extend(
        f"{item.finding_id}  {item.status}  {item.risk.level}  {item.savings.potential_savings}"
        for item in (findings or [])
    )
    lines.append("")
    lines.append(
        f"Completed scopes: {len(inventory.completed)}; failed scopes: {len(inventory.failed)}"
    )
    lines.extend(
        f"Issue: {issue.scope} {issue.operation} {issue.category}" for issue in inventory.issues
    )
    return "\n".join(lines) + "\n"


def render_saved_json(saved: dict[str, Any], command: str, finding_id: str | None = None) -> str:
    view = _saved_view(saved, command, finding_id)
    return json.dumps(view, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_saved_table(saved: dict[str, Any], command: str, finding_id: str | None = None) -> str:
    view = _saved_view(saved, command, finding_id)
    if command == "explain":
        finding = view["finding"]
        risk = finding["risk"]
        savings = finding["savings"]
        lines = [
            f"Finding: {finding['finding_id']}",
            f"Status: {finding['status']}",
            f"Risk: {risk['level']}",
            f"Reasons: {', '.join(risk['reasons']) or 'none'}",
            f"Unknown factors: {', '.join(risk['unknown_factors']) or 'none'}",
            f"Explanation: {finding['explanation']}",
            "Evidence:",
        ]
        lines.extend(
            f"  {item['metric']}: {item['value']} {item['unit'] or ''} "
            f"({item['quality']}, {item['period_start'] or '?'} to {item['period_end'] or '?'})"
            for item in finding["evidence"]
        )
        lines.extend(
            [
                f"Savings: {savings['potential_savings']} {savings['currency']} "
                f"per {savings['period']}",
                f"Baseline: {savings['baseline']}; optimized: {savings['optimized']}",
                f"Confidence: {savings['confidence']}",
                f"Formula: {savings['formula']}",
                f"Assumptions: {'; '.join(savings['assumptions']) or 'none'}",
                f"Excluded costs: {'; '.join(savings['excluded_costs']) or 'none'}",
                f"Data sources: {'; '.join(savings['data_sources']) or 'none'}",
            ]
        )
    else:
        lines = [
            f"{view['data_kind']} report: {view['status']}",
            f"Scanned at: {view['scanned_at']}",
        ]
        if view["data_kind"] == "DEMO":
            lines.insert(0, "DEMO DATA — CloudSaver")
        if "analysis_status" in view:
            lines.append(f"Analysis: {view['analysis_status']}")
        lines.extend(
            [
                f"Completed scopes: {len(view['scope']['completed'])}; "
                f"failed scopes: {len(view['scope']['failed'])}",
                "",
                "FINDING ID  STATUS  RISK  SAVINGS",
            ]
        )
        lines.extend(
            f"{item['finding_id']}  {item['status']}  {item['risk']['level']}  "
            f"{item['savings']['potential_savings']}"
            for item in view["findings"]
        )
        lines.extend(
            f"Issue: {item['scope']} {item['operation']} {item['category']}"
            for item in view["collection_issues"]
        )
    return "\n".join(lines) + "\n"


def _saved_view(saved: dict[str, Any], command: str, finding_id: str | None) -> dict[str, Any]:
    if command == "report":
        return saved
    header = {key: saved[key] for key in ("schema_version", "data_kind", "scanned_at", "status")}
    if saved["data_kind"] == "DEMO":
        header["notice"] = "DEMO DATA"
    if command == "explain":
        finding = next(
            (item for item in saved["findings"] if item["finding_id"] == finding_id), None
        )
        if finding is None:
            raise ValueError("finding ID was not found")
        header["finding"] = finding
        return header
    if command == "opportunities":
        header["scope"] = saved["scope"]
        header["collection_issues"] = saved["collection_issues"]
        if "analysis_status" in saved:
            header["analysis_status"] = saved["analysis_status"]
        header["findings"] = [item for item in saved["findings"] if item["status"] == "CANDIDATE"]
        return header
    raise ValueError("unsupported report command")
