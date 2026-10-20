"""Phase 4 cost and report commands run entirely from local data."""

import json
import socket
from dataclasses import asdict
from pathlib import Path

import pytest

from cloudsaver.cli import main
from cloudsaver.costs import apply_scenarios, calculate
from cloudsaver.demo import scan
from cloudsaver.domain import ResourceSnapshot
from cloudsaver.providers.aws import Inventory
from cloudsaver.report import document, inventory_document
from cloudsaver.stored import read_report


def _scenario(finding_id: str, policy: str) -> dict[str, object]:
    values = {
        "low_utilization_ec2": [
            ("compute", "20.00", "0.00"),
            ("ebs", "5.00", "5.00"),
            ("ipv4", "3.00", "3.00"),
        ],
        "unattached_ebs": [("ebs", "5.25", "0.00")],
        "potential_unused_public_ipv4": [("ipv4", "3.75", "0.00")],
    }
    return {
        "finding_id": finding_id,
        "currency": "USD",
        "region": "ap-northeast-2",
        "source": "AWS_PRICING",
        "as_of": "2026-10-01T00:00:00Z",
        "components": [
            {"kind": kind, "baseline": before, "optimized": after}
            for kind, before, after in values[policy]
        ],
    }


def _report_file(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    observed_at, findings = scan()
    report = document(observed_at, findings)
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def test_ec2_arithmetic_keeps_ebs_and_ipv4_costs() -> None:
    estimate = calculate("low_utilization_ec2", _scenario("id", "low_utilization_ec2"))
    assert estimate.baseline == "28.00"
    assert estimate.optimized == "8.00"
    assert estimate.potential_savings == "20.00"
    assert estimate.confidence == "CONDITIONAL"
    assert "baseline" in estimate.formula
    assert "EBS and public IPv4 charges continue" in " ".join(estimate.assumptions)
    assert asdict(estimate)["period"] == "MONTH"


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("unattached_ebs", "5.25"), ("potential_unused_public_ipv4", "3.75")],
)
def test_other_policy_arithmetic(policy: str, expected: str) -> None:
    estimate = calculate(policy, _scenario("id", policy))
    assert estimate.potential_savings == expected
    assert estimate.optimized == "0.00"


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("source", "UNKNOWN"),
        ("currency", "usd"),
        ("region", "not-a-region"),
        ("as_of", "2026-10-01"),
        ("components", [{"kind": "compute", "baseline": "20", "optimized": "0"}]),
    ],
)
def test_incomplete_scenario_is_rejected(change: str, value: object) -> None:
    scenario = _scenario("id", "low_utilization_ec2")
    scenario[change] = value
    with pytest.raises(ValueError):
        calculate("low_utilization_ec2", scenario)


def test_negative_invalid_and_residual_costs_are_rejected() -> None:
    scenario = _scenario("id", "low_utilization_ec2")
    components = scenario["components"]
    assert isinstance(components, list)
    components[0]["baseline"] = "-1.00"
    with pytest.raises(ValueError):
        calculate("low_utilization_ec2", scenario)
    components[0]["baseline"] = "20.001"
    with pytest.raises(ValueError):
        calculate("low_utilization_ec2", scenario)
    components[0]["baseline"] = "2e1"
    with pytest.raises(ValueError):
        calculate("low_utilization_ec2", scenario)
    components[0]["baseline"] = "20.00"
    components[1]["optimized"] = "0.00"
    with pytest.raises(ValueError):
        calculate("low_utilization_ec2", scenario)


def test_costs_only_apply_to_candidates_and_leave_unknowns() -> None:
    observed_at, findings = scan()
    report = document(observed_at, findings)
    candidate = next(item for item in report["findings"] if item["resource"]["ref"] == "i-demo-dev")
    protected = next(item for item in report["findings"] if item["status"] == "EXCLUDED")
    scenario = _scenario(candidate["finding_id"], "low_utilization_ec2")
    enriched = apply_scenarios(report, {"schema_version": "1.0.0", "scenarios": [scenario]})
    calculated = next(
        item for item in enriched["findings"] if item["finding_id"] == candidate["finding_id"]
    )
    assert calculated["savings"]["potential_savings"] == "20.00"
    assert candidate["savings"]["potential_savings"] == "UNKNOWN"
    assert protected["savings"]["potential_savings"] == "UNKNOWN"
    with pytest.raises(ValueError):
        apply_scenarios(
            report,
            {
                "schema_version": "1.0.0",
                "scenarios": [_scenario(protected["finding_id"], "low_utilization_ec2")],
            },
        )
    assert enriched["data_kind"] == "DEMO"


def test_cost_region_must_match_finding() -> None:
    observed_at, findings = scan()
    report = document(observed_at, findings)
    candidate = next(item for item in report["findings"] if item["status"] == "CANDIDATE")
    scenario = _scenario(candidate["finding_id"], candidate["policy_id"])
    scenario["region"] = "us-east-1"
    with pytest.raises(ValueError):
        apply_scenarios(report, {"schema_version": "1.0.0", "scenarios": [scenario]})


def test_saved_report_commands_are_offline_and_keep_statuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, original = _report_file(tmp_path)

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network used for saved report")

    monkeypatch.setattr(socket, "socket", blocked)
    candidate = next(
        item for item in original["findings"] if item["resource"]["ref"] == "i-demo-dev"
    )
    costs = tmp_path / "costs.json"
    costs.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "scenarios": [_scenario(candidate["finding_id"], "low_utilization_ec2")],
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "explain",
                candidate["finding_id"],
                "--input",
                str(path),
                "--cost-input",
                str(costs),
                "--format",
                "json",
            ]
        )
        == 0
    )
    explained = json.loads(capsys.readouterr().out)
    assert explained["finding"]["savings"]["potential_savings"] == "20.00"
    assert explained["finding"]["risk"]["level"] == "MEDIUM"
    assert explained["notice"] == "DEMO DATA"
    assert main(["opportunities", "--input", str(path), "--format", "json"]) == 0
    opportunities = json.loads(capsys.readouterr().out)
    assert all(item["status"] == "CANDIDATE" for item in opportunities["findings"])
    assert len(opportunities["findings"]) == 3
    assert main(["report", "--input", str(path), "--format", "json"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert len(full["findings"]) == 5
    assert full["schema_version"] == "1.1.0"


def test_legacy_report_loads_and_unknowns_remain_unknown(tmp_path: Path) -> None:
    path, original = _report_file(tmp_path)
    original["schema_version"] = "1.0.0"
    for item in original["findings"]:
        item["savings"].pop("formula")
    path.write_text(json.dumps(original), encoding="utf-8")
    loaded = read_report(path)
    assert loaded["findings"][0]["savings"]["formula"] == "UNKNOWN"
    assert all(item["savings"]["potential_savings"] == "UNKNOWN" for item in loaded["findings"])


def test_invalid_report_and_missing_finding_return_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = _report_file(tmp_path)
    assert main(["explain", "missing", "--input", str(path)]) == 2
    assert "finding" in capsys.readouterr().err
    path.write_text("{}", encoding="utf-8")
    assert main(["report", "--input", str(path)]) == 2
    assert main(["report", "--input", str(tmp_path / "absent.json")]) == 2


def test_malformed_report_types_fail_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, original = _report_file(tmp_path)
    for change in ("schema_version", "status", "risk_level"):
        altered = json.loads(json.dumps(original))
        if change == "risk_level":
            altered["findings"][0]["risk"]["level"] = []
        else:
            altered[change] = []
        path.write_text(json.dumps(altered), encoding="utf-8")
        assert main(["report", "--input", str(path)]) == 2
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err
        assert captured.out == ""


def test_saved_report_drops_unexpected_fields(tmp_path: Path) -> None:
    path, original = _report_file(tmp_path)
    original["secret"] = "do-not-show"
    original["findings"][0]["tags"] = {"secret": "do-not-show"}
    path.write_text(json.dumps(original), encoding="utf-8")
    rendered = json.dumps(read_report(path))
    assert "do-not-show" not in rendered


def test_saved_aws_report_keeps_resources_and_redacts_sensitive_fields(tmp_path: Path) -> None:
    resource = ResourceSnapshot(
        "vol-example",
        "ebs_volume",
        "ap-northeast-2",
        {"secret": "sensitive-value"},
        "available",
        account_ref="123456789012",
    )
    raw = inventory_document(Inventory("2026-10-01T00:00:00Z", "123456789012", [resource]), [])
    raw["unexpected_secret"] = "sensitive-value"
    path = tmp_path / "aws.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    saved = read_report(path)
    rendered = json.dumps(saved)
    assert saved["resources"][0]["resource_id"] == "vol-example"
    assert saved["account_ref"] == "REDACTED"
    assert "123456789012" not in rendered
    assert "sensitive-value" not in rendered
