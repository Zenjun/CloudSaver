"""Opportunity rules use local snapshots only; no AWS account is accessed."""

import json
from dataclasses import replace

import pytest

from cloudsaver.cli import main
from cloudsaver.domain import ResourceSnapshot
from cloudsaver.policies import evaluate, evaluate_all
from cloudsaver.providers.aws import Inventory
from cloudsaver.report import inventory_document

REGION = "ap-northeast-2"
START = "2026-10-01T00:00:00Z"
END = "2026-10-15T00:00:00Z"


def instance(**changes: object) -> ResourceSnapshot:
    base = ResourceSnapshot(
        "i-example",
        "ec2_instance",
        REGION,
        {},
        "running",
        cpu_average=5.0,
        cpu_samples=7,
        period_start=START,
        period_end=END,
        metrics_status="COMPLETE",
        account_ref="123456789012",
    )
    return replace(base, **changes)


def test_low_cpu_boundary_and_above_threshold() -> None:
    candidate = evaluate(instance(), provider="aws")
    assert candidate is not None and candidate.status == "CANDIDATE"
    assert candidate.policy_id == "low_utilization_ec2"
    assert [item.metric for item in candidate.evidence] == [
        "CPUUtilization.average",
        "CPUUtilization.samples",
        "observation_days",
    ]
    assert candidate.evidence[0].period_start == START
    assert candidate.evidence[2].value == 14
    assert candidate.savings.potential_savings == "UNKNOWN"
    assert evaluate(instance(cpu_average=5.01), provider="aws") is None
    assert evaluate(instance(state="stopped"), provider="aws") is None


@pytest.mark.parametrize(
    ("changes", "quality"),
    [
        ({"cpu_average": None, "cpu_samples": 0, "metrics_status": "MISSING"}, "MISSING"),
        ({"cpu_average": 0.0, "metrics_status": "ERROR"}, "ERROR"),
        ({"cpu_average": 0.0, "cpu_samples": 6}, "COMPLETE"),
        ({"cpu_average": 0.0, "period_start": "2026-10-02T00:00:00Z"}, "COMPLETE"),
        ({"cpu_average": 0.0, "period_start": None}, "COMPLETE"),
        ({"cpu_average": 0.0, "metrics_status": "NOT_REQUESTED"}, "MISSING"),
        ({"cpu_average": float("nan")}, "MISSING"),
    ],
)
def test_missing_or_invalid_observations_are_not_zero_usage(
    changes: dict[str, object], quality: str
) -> None:
    finding = evaluate(instance(**changes), provider="aws")
    assert finding is not None and finding.status == "INSUFFICIENT_DATA"
    assert finding.evidence[0].quality == quality
    assert finding.risk.level == "UNKNOWN"


def test_protection_and_retention_exclude_and_tags_are_not_serialized() -> None:
    protected_resource = instance(
        tags={" Protected ": " YES ", "protected": "false", "secret": "sensitive-value"}
    )
    protected = evaluate(protected_resource, provider="aws")
    production = evaluate(
        instance(tags={"Environment": "Production", "environment": "dev"}), provider="aws"
    )
    volume = ResourceSnapshot("vol-example", "ebs_volume", REGION, {"retain": "true"}, "available")
    retained = evaluate(volume, provider="aws")
    assert protected is not None and protected.status == "EXCLUDED"
    assert protected.risk.level == "CRITICAL"
    assert production is not None and production.status == "EXCLUDED"
    assert production.risk.level == "HIGH"
    assert retained is not None and retained.status == "EXCLUDED"
    assert retained.risk.reasons == ["retention_tag"]
    report = json.dumps(
        inventory_document(
            Inventory(END, resources=[volume, protected_resource]), [retained, protected]
        )
    )
    assert "sensitive-value" not in report
    assert "123456789012" not in report


def test_ebs_ipv4_and_deterministic_order() -> None:
    volume = ResourceSnapshot("vol-example", "ebs_volume", REGION, {}, "available")
    address = ResourceSnapshot("eipalloc-example", "elastic_ip", REGION, {}, "unassociated")
    first = evaluate_all([volume, address], provider="aws")
    assert first == evaluate_all([address, volume], provider="aws")
    assert {item.policy_id for item in first} == {"unattached_ebs", "potential_unused_public_ipv4"}
    assert all(item.risk.level == "UNKNOWN" for item in first)
    assert (
        "data_retention"
        in next(item for item in first if item.policy_id == "unattached_ebs").risk.unknown_factors
    )
    assert evaluate(replace(volume, state="in-use"), provider="aws") is None
    assert evaluate(replace(address, state="associated"), provider="aws") is None


def test_partial_and_failed_collection_keep_analysis_status_explicit() -> None:
    volume = ResourceSnapshot("vol-example", "ebs_volume", REGION, {}, "available")
    inventory = Inventory(
        END,
        resources=[volume],
        requested=[f"{REGION}:describe_volumes", f"{REGION}:describe_instances"],
        completed=[f"{REGION}:describe_volumes"],
        failed=[f"{REGION}:describe_instances"],
    )
    partial = inventory_document(inventory, evaluate_all(inventory.resources, provider="aws"))
    assert partial["status"] == "PARTIAL"
    assert partial["analysis_status"] == "PARTIAL"
    assert len(partial["findings"]) == 1
    assert partial["scope"]["failed"] == [f"{REGION}:describe_instances"]
    inventory.completed = []
    inventory.resources = []
    failed = inventory_document(inventory, [])
    assert failed["status"] == "FAILED"
    assert failed["analysis_status"] == "NOT_EVALUATED"


def test_aws_cli_renders_findings_from_mocked_collection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    volume = ResourceSnapshot("vol-example", "ebs_volume", REGION, {}, "available")
    inventory = Inventory(
        END,
        resources=[volume],
        requested=[f"{REGION}:describe_volumes"],
        completed=[f"{REGION}:describe_volumes"],
    )
    monkeypatch.setattr("cloudsaver.providers.aws.new_session", lambda *_: object())
    monkeypatch.setattr("cloudsaver.providers.aws.collect", lambda *_: inventory)
    assert main(["scan", "--regions", REGION, "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["analysis_status"] == "COMPLETE"
    assert result["findings"][0]["policy_id"] == "unattached_ebs"
