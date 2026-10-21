"""Offline, fail-closed review of a hypothetical action on one finding."""

import json
from typing import Any

ACTION_BY_POLICY = {
    "low_utilization_ec2": "STOP_EC2",
    "unattached_ebs": "DELETE_EBS",
    "potential_unused_public_ipv4": "RELEASE_ELASTIC_IP",
}
DESTRUCTIVE_ACTIONS = {"DELETE_EBS", "RELEASE_ELASTIC_IP"}


def review_finding(saved: dict[str, Any], finding_id: str) -> dict[str, Any]:
    """Return review blockers. This function can never authorize execution."""
    finding = next((item for item in saved["findings"] if item["finding_id"] == finding_id), None)
    if finding is None:
        raise ValueError("finding ID was not found")
    action = ACTION_BY_POLICY.get(finding["policy_id"], "UNSUPPORTED")
    blockers = []
    if saved["data_kind"] != "AWS":
        blockers.append("DEMO_REPORT")
    if saved["status"] != "COMPLETE" or saved["scope"]["failed"]:
        blockers.append("COLLECTION_INCOMPLETE")
    if saved.get("analysis_status") != "COMPLETE" and saved["data_kind"] == "AWS":
        blockers.append("ANALYSIS_INCOMPLETE")
    if finding["status"] != "CANDIDATE":
        blockers.append("NOT_CANDIDATE")
    if finding["risk"]["level"] in {"HIGH", "CRITICAL", "UNKNOWN"}:
        blockers.append("RISK_NOT_ACCEPTABLE")
    if finding["risk"]["unknown_factors"]:
        blockers.append("DEPENDENCIES_UNVERIFIED")
    if not finding["evidence"] or any(
        item["quality"] != "COMPLETE" for item in finding["evidence"]
    ):
        blockers.append("EVIDENCE_INCOMPLETE")
    if action == "UNSUPPORTED":
        blockers.append("ACTION_UNSUPPORTED")
    if action in DESTRUCTIVE_ACTIONS:
        blockers.append("DESTRUCTIVE_ACTION_EXCLUDED")
    blockers.extend(
        (
            "TRUSTED_IDENTITY_UNAVAILABLE",
            "ACCOUNT_TARGET_UNBOUND",
            "LIVE_STATE_NOT_RECHECKED",
            "EXECUTION_DISABLED",
        )
    )
    return {
        "schema_version": "1.0.0",
        "data_kind": "ACTION_REVIEW",
        "review_status": "BLOCKED",
        "execution_ready": False,
        "source_data_kind": saved["data_kind"],
        "finding_id": finding_id,
        "finding_status": finding["status"],
        "risk_level": finding["risk"]["level"],
        "considered_action": action,
        "blockers": blockers,
        "notice": "Offline review only. No approval or AWS write operation exists.",
    }


def render_review_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_review_table(result: dict[str, Any]) -> str:
    lines = [
        f"Action review: {result['review_status']} (execution disabled)",
        f"Finding: {json.dumps(result['finding_id'], ensure_ascii=True)}",
        f"Considered action: {result['considered_action']}",
        f"Finding status: {result['finding_status']}; risk: {result['risk_level']}",
        "Blockers:",
    ]
    lines.extend(f"  - {blocker}" for blocker in result["blockers"])
    lines.append(result["notice"])
    return "\n".join(lines) + "\n"
