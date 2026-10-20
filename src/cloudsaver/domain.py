"""Small validated models shared by demo analysis and later collectors."""

from dataclasses import dataclass, field
from typing import Any, Literal, cast

ResourceType = Literal["ec2_instance", "ebs_volume", "elastic_ip"]
MetricsStatus = Literal["COMPLETE", "MISSING", "ERROR", "NOT_REQUESTED"]


@dataclass(frozen=True)
class ResourceSnapshot:
    resource_id: str
    type: ResourceType
    region: str
    tags: dict[str, str]
    state: str
    cpu_average: float | None = None
    cpu_samples: int = 0
    period_start: str | None = None
    period_end: str | None = None
    account_ref: str | None = None
    observed_at: str | None = None
    metrics_status: MetricsStatus = "NOT_REQUESTED"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "ResourceSnapshot":
        resource_id = raw.get("resource_id")
        kind = raw.get("type")
        region = raw.get("region")
        state = raw.get("state")
        tags = raw.get("tags")
        if (
            not isinstance(resource_id, str)
            or not resource_id
            or not isinstance(region, str)
            or not region
            or not isinstance(state, str)
            or not state
        ):
            raise ValueError("invalid resource identity or state")
        if kind not in ("ec2_instance", "ebs_volume", "elastic_ip"):
            raise ValueError("unsupported resource type")
        if not isinstance(tags, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in tags.items()
        ):
            raise ValueError("invalid resource tags")
        average = raw.get("cpu_average")
        if average is not None and (
            isinstance(average, bool) or not isinstance(average, (int, float))
        ):
            raise ValueError("invalid CPU average")
        samples = raw.get("cpu_samples", 0)
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 0:
            raise ValueError("invalid CPU sample count")
        start = raw.get("period_start")
        end = raw.get("period_end")
        if (start is not None and not isinstance(start, str)) or (
            end is not None and not isinstance(end, str)
        ):
            raise ValueError("invalid observation period")
        metrics_status = raw.get("metrics_status", "NOT_REQUESTED")
        if metrics_status not in ("COMPLETE", "MISSING", "ERROR", "NOT_REQUESTED"):
            raise ValueError("invalid metrics status")
        return cls(
            resource_id=resource_id,
            type=kind,
            region=region,
            tags=tags,
            state=state,
            cpu_average=float(average) if average is not None else None,
            cpu_samples=samples,
            period_start=start,
            period_end=end,
            metrics_status=cast(MetricsStatus, metrics_status),
        )


@dataclass(frozen=True)
class Evidence:
    source: str
    metric: str
    value: float | str | None
    unit: str | None
    quality: Literal["COMPLETE", "MISSING", "ERROR"]
    period_start: str | None = None
    period_end: str | None = None


@dataclass(frozen=True)
class RiskAssessment:
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
    reasons: list[str] = field(default_factory=list)
    unknown_factors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SavingsEstimate:
    currency: str = "UNKNOWN"
    period: str = "MONTH"
    baseline: str = "UNKNOWN"
    optimized: str = "UNKNOWN"
    potential_savings: str = "UNKNOWN"
    confidence: str = "UNKNOWN"
    assumptions: list[str] = field(default_factory=list)
    excluded_costs: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Finding:
    finding_id: str
    policy_id: str
    status: Literal["CANDIDATE", "EXCLUDED", "INSUFFICIENT_DATA"]
    resource_type: ResourceType
    resource_ref: str
    evidence: list[Evidence]
    risk: RiskAssessment
    savings: SavingsEstimate
    explanation: str
