"""Offline fixture and illustrative rules for the Phase 1 demo."""

import json
from importlib.resources import files
from typing import Any, Literal

from cloudsaver.domain import Evidence, Finding, ResourceSnapshot, RiskAssessment, SavingsEstimate


def _risk(resource: ResourceSnapshot, *, data_retention_unknown: bool = False) -> RiskAssessment:
    tags = {key.lower(): value.lower() for key, value in resource.tags.items()}
    if tags.get("protected") in {"true", "yes", "1"} or tags.get("critical") in {
        "true",
        "yes",
        "1",
    }:
        return RiskAssessment("CRITICAL", ["protected_or_critical_tag"])
    if tags.get("environment") in {"prod", "production"}:
        return RiskAssessment("HIGH", ["production_environment"])
    unknown = ["application_dependencies"]
    if data_retention_unknown:
        unknown.append("data_retention")
    if tags.get("environment") == "dev":
        return RiskAssessment("MEDIUM", ["development_environment"], unknown)
    return RiskAssessment("UNKNOWN", [], unknown + ["environment"])


def _finding(
    resource: ResourceSnapshot,
    policy_id: str,
    status: Literal["CANDIDATE", "EXCLUDED", "INSUFFICIENT_DATA"],
    evidence: list[Evidence],
    explanation: str,
    *,
    data_retention_unknown: bool = False,
) -> Finding:
    risk = _risk(resource, data_retention_unknown=data_retention_unknown)
    if risk.level in {"HIGH", "CRITICAL"}:
        status = "EXCLUDED"
    return Finding(
        finding_id=f"demo:{policy_id}:{resource.resource_id}",
        policy_id=policy_id,
        status=status,
        resource_type=resource.type,
        resource_ref=resource.resource_id,
        evidence=evidence,
        risk=risk,
        savings=SavingsEstimate(
            assumptions=["No pricing or billing data is available in demo mode."],
            excluded_costs=(
                ["EBS and public IPv4 charges may continue after stopping EC2."]
                if resource.type == "ec2_instance"
                else []
            ),
        ),
        explanation=explanation,
    )


def _analyze(resource: ResourceSnapshot) -> Finding | None:
    if resource.type == "ec2_instance" and resource.state == "running":
        evidence = [
            Evidence(
                source="demo_fixture",
                metric="CPUUtilization.average",
                value=resource.cpu_average,
                unit="percent",
                quality="COMPLETE" if resource.cpu_average is not None else "MISSING",
                period_start=resource.period_start,
                period_end=resource.period_end,
            ),
            Evidence(
                "demo_fixture",
                "CPUUtilization.samples",
                resource.cpu_samples,
                "count",
                "COMPLETE" if resource.cpu_samples > 0 else "MISSING",
            ),
        ]
        if resource.cpu_average is None or resource.cpu_samples < 7:
            return _finding(
                resource,
                "low_utilization_ec2",
                "INSUFFICIENT_DATA",
                evidence,
                "CPU observations are missing or too sparse; zero usage is not assumed.",
            )
        if resource.cpu_average <= 5:
            return _finding(
                resource,
                "low_utilization_ec2",
                "CANDIDATE",
                evidence,
                "Low CPU is only a review signal; network, disk and workload context are unknown.",
            )
    if resource.type == "ebs_volume" and resource.state == "available":
        return _finding(
            resource,
            "unattached_ebs",
            "CANDIDATE",
            [Evidence("demo_fixture", "volume_state", resource.state, None, "COMPLETE")],
            "The volume is unattached, but its data retention purpose is unknown.",
            data_retention_unknown=True,
        )
    if resource.type == "elastic_ip" and resource.state == "unassociated":
        return _finding(
            resource,
            "potential_unused_public_ipv4",
            "CANDIDATE",
            [Evidence("demo_fixture", "association_state", resource.state, None, "COMPLETE")],
            "This Elastic IP is unassociated; future use or dependencies need review.",
        )
    return None


def scan() -> tuple[str, list[Finding]]:
    """Load bundled fictional data; this function has no AWS or network path."""
    raw: Any = json.loads(files("cloudsaver").joinpath("data/demo.json").read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid demo fixture")
    observed_at = raw.get("observed_at")
    resources = raw.get("resources")
    if not isinstance(observed_at, str) or not isinstance(resources, list):
        raise ValueError("invalid demo fixture")
    findings = []
    for item in resources:
        if not isinstance(item, dict):
            raise ValueError("invalid demo resource")
        finding = _analyze(ResourceSnapshot.from_mapping(item))
        if finding is not None:
            findings.append(finding)
    return observed_at, sorted(findings, key=lambda finding: finding.finding_id)
