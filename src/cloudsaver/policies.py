"""Conservative, deterministic opportunity hypotheses for demo and AWS snapshots."""

from collections.abc import Iterable
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal

from cloudsaver.domain import Evidence, Finding, ResourceSnapshot, RiskAssessment, SavingsEstimate

CPU_MAX_PERCENT = 5.0
CPU_MIN_SAMPLES = 7
CPU_MIN_DAYS = 14
Provider = Literal["demo", "aws"]
FindingStatus = Literal["CANDIDATE", "EXCLUDED", "INSUFFICIENT_DATA"]


def _tag_values(resource: ResourceSnapshot, name: str) -> set[str]:
    return {
        value.strip().lower() for key, value in resource.tags.items() if key.strip().lower() == name
    }


def _risk(
    resource: ResourceSnapshot, *, retention_unknown: bool = False, insufficient: bool = False
) -> RiskAssessment:
    affirmative = {"true", "yes", "1"}
    if (_tag_values(resource, "protected") | _tag_values(resource, "critical")) & affirmative:
        return RiskAssessment("CRITICAL", ["protected_or_critical_tag"])
    if _tag_values(resource, "importance") & {"high", "critical"}:
        return RiskAssessment("HIGH", ["high_importance_tag"])
    environment = _tag_values(resource, "environment")
    if environment & {"prod", "production"}:
        return RiskAssessment("HIGH", ["production_environment"])
    if resource.type == "ec2_instance" and _tag_values(resource, "aws:autoscaling:groupname"):
        return RiskAssessment("HIGH", ["autoscaling_group_membership"])
    if resource.type == "ebs_volume" and any(
        _tag_values(resource, key) & affirmative for key in ("retain", "retention", "do-not-delete")
    ):
        return RiskAssessment("HIGH", ["retention_tag"])
    unknown = ["application_dependencies"]
    if resource.type == "ec2_instance":
        unknown.extend(["load_balancer_registration", "network_and_disk_usage"])
    if retention_unknown:
        unknown.append("data_retention")
    if insufficient:
        unknown.append("observation_completeness")
        return RiskAssessment("UNKNOWN", [], unknown)
    if retention_unknown:
        return RiskAssessment("UNKNOWN", [], unknown)
    if environment & {"dev", "development"}:
        return RiskAssessment("MEDIUM", ["development_environment"], unknown)
    return RiskAssessment("UNKNOWN", [], unknown + ["environment"])


def _finding(
    resource: ResourceSnapshot,
    provider: Provider,
    policy_id: str,
    status: FindingStatus,
    evidence: list[Evidence],
    explanation: str,
    *,
    retention_unknown: bool = False,
) -> Finding:
    risk = _risk(
        resource, retention_unknown=retention_unknown, insufficient=status == "INSUFFICIENT_DATA"
    )
    if risk.level in {"HIGH", "CRITICAL"}:
        status = "EXCLUDED"
        explanation += " Protection or retention tags exclude this resource from the candidate set."
    return Finding(
        finding_id=f"{provider}:{policy_id}:{resource.region}:{resource.resource_id}",
        policy_id=policy_id,
        status=status,
        resource_type=resource.type,
        resource_ref=resource.resource_id,
        evidence=evidence,
        risk=risk,
        savings=SavingsEstimate(
            assumptions=["Pricing and billing data have not been collected."],
            excluded_costs=(
                ["EBS and public IPv4 charges may continue after stopping EC2."]
                if resource.type == "ec2_instance"
                else []
            ),
        ),
        explanation=explanation,
    )


def _observation_days(resource: ResourceSnapshot) -> float | None:
    if not resource.period_start or not resource.period_end:
        return None
    try:
        start = datetime.fromisoformat(resource.period_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(resource.period_end.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or end < start:
            return None
        return (end - start) / timedelta(days=1)
    except ValueError:
        return None


def evaluate(resource: ResourceSnapshot, *, provider: Provider) -> Finding | None:
    """Emit review signals only; no policy here authorizes an AWS action."""
    source = "demo_fixture" if provider == "demo" else "cloudwatch_get_metric_data"
    if resource.type == "ec2_instance" and resource.state == "running":
        average = resource.cpu_average
        valid_average = average is not None and isfinite(average) and 0 <= average <= 100
        days = _observation_days(resource)
        metric_complete = resource.metrics_status == "COMPLETE"
        quality: Literal["COMPLETE", "MISSING", "ERROR"] = (
            "ERROR"
            if resource.metrics_status == "ERROR"
            else "COMPLETE"
            if metric_complete and valid_average
            else "MISSING"
        )
        evidence = [
            Evidence(
                source,
                "CPUUtilization.average",
                average,
                "percent",
                quality,
                resource.period_start,
                resource.period_end,
            ),
            Evidence(
                source,
                "CPUUtilization.samples",
                float(resource.cpu_samples),
                "count",
                quality if resource.cpu_samples > 0 else "MISSING",
                resource.period_start,
                resource.period_end,
            ),
            Evidence(
                source,
                "observation_days",
                days,
                "days",
                "COMPLETE" if days is not None else "MISSING",
                resource.period_start,
                resource.period_end,
            ),
        ]
        if (
            not metric_complete
            or not valid_average
            or resource.cpu_samples < CPU_MIN_SAMPLES
            or days is None
            or days < CPU_MIN_DAYS
        ):
            return _finding(
                resource,
                provider,
                "low_utilization_ec2",
                "INSUFFICIENT_DATA",
                evidence,
                "CPU observations are missing, invalid, or too sparse for the 14-day rule; "
                "zero usage is not assumed.",
            )
        if average is not None and average <= CPU_MAX_PERCENT:
            return _finding(
                resource,
                provider,
                "low_utilization_ec2",
                "CANDIDATE",
                evidence,
                "CPU is at or below 5% across the observation window. This is only a review "
                "signal; network, disk, workload, and commitments are unknown.",
            )
    if resource.type == "ebs_volume" and resource.state == "available":
        return _finding(
            resource,
            provider,
            "unattached_ebs",
            "CANDIDATE",
            [
                Evidence(
                    "demo_fixture" if provider == "demo" else "ec2_describe_volumes",
                    "volume_state",
                    resource.state,
                    None,
                    "COMPLETE",
                )
            ],
            "The volume is unattached, but its data retention purpose is unknown.",
            retention_unknown=True,
        )
    if resource.type == "elastic_ip" and resource.state == "unassociated":
        return _finding(
            resource,
            provider,
            "potential_unused_public_ipv4",
            "CANDIDATE",
            [
                Evidence(
                    "demo_fixture" if provider == "demo" else "ec2_describe_addresses",
                    "association_state",
                    resource.state,
                    None,
                    "COMPLETE",
                )
            ],
            "This Elastic IP is unassociated; future use and dependencies need review.",
        )
    return None


def evaluate_all(resources: Iterable[ResourceSnapshot], *, provider: Provider) -> list[Finding]:
    findings = (evaluate(resource, provider=provider) for resource in resources)
    return sorted(
        (finding for finding in findings if finding is not None),
        key=lambda item: item.finding_id,
    )
