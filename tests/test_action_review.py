"""Phase 8 offline reviews must always fail closed."""

import json
import socket
import stat
from pathlib import Path

import pytest

from cloudsaver.action_review import review_finding
from cloudsaver.cli import main
from cloudsaver.demo import scan
from cloudsaver.report import document


def _demo_report(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    observed_at, findings = scan()
    report = document(observed_at, findings)
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path, report


def test_demo_review_is_blocked_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path, report = _demo_report(tmp_path)
    finding = next(item for item in report["findings"] if item["status"] == "CANDIDATE")

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("review must not use network")

    monkeypatch.setattr(socket, "socket", blocked)
    assert (
        main(["action-review", finding["finding_id"], "--input", str(path), "--format", "json"])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["review_status"] == "BLOCKED"
    assert result["execution_ready"] is False
    assert "DEMO_REPORT" in result["blockers"]
    assert "TRUSTED_IDENTITY_UNAVAILABLE" in result["blockers"]
    assert "LIVE_STATE_NOT_RECHECKED" in result["blockers"]
    assert "EXECUTION_DISABLED" in result["blockers"]


def test_excluded_and_destructive_findings_are_blocked(tmp_path: Path) -> None:
    _, report = _demo_report(tmp_path)
    excluded = next(item for item in report["findings"] if item["status"] == "EXCLUDED")
    result = review_finding(report, excluded["finding_id"])
    assert "NOT_CANDIDATE" in result["blockers"]
    assert result["execution_ready"] is False

    volume = next(
        item
        for item in report["findings"]
        if item["policy_id"] == "unattached_ebs" and item["status"] == "CANDIDATE"
    )
    result = review_finding(report, volume["finding_id"])
    assert result["considered_action"] == "DELETE_EBS"
    assert "DESTRUCTIVE_ACTION_EXCLUDED" in result["blockers"]


def test_forged_complete_report_cannot_approve_execution(tmp_path: Path) -> None:
    _, report = _demo_report(tmp_path)
    finding = next(item for item in report["findings"] if item["status"] == "CANDIDATE")
    report.update(
        {
            "data_kind": "AWS",
            "status": "COMPLETE",
            "analysis_status": "COMPLETE",
            "account_ref": "REDACTED",
            "resources": [],
            "execution_ready": True,
        }
    )
    finding["risk"] = {"level": "LOW", "reasons": [], "unknown_factors": []}
    finding["evidence"] = [
        {
            "source": "fixture",
            "metric": "observation_days",
            "value": 14,
            "unit": "days",
            "quality": "COMPLETE",
            "period_start": None,
            "period_end": None,
        }
    ]
    result = review_finding(report, finding["finding_id"])
    assert result["source_data_kind"] == "AWS"
    assert "DEMO_REPORT" not in result["blockers"]
    assert result["review_status"] == "BLOCKED"
    assert result["execution_ready"] is False
    assert "ACCOUNT_TARGET_UNBOUND" in result["blockers"]


def test_partial_or_unknown_evidence_adds_blockers(tmp_path: Path) -> None:
    _, report = _demo_report(tmp_path)
    finding = next(item for item in report["findings"] if item["status"] == "INSUFFICIENT_DATA")
    report["status"] = "PARTIAL"
    result = review_finding(report, finding["finding_id"])
    assert "COLLECTION_INCOMPLETE" in result["blockers"]
    assert "NOT_CANDIDATE" in result["blockers"]
    assert "RISK_NOT_ACCEPTABLE" in result["blockers"]
    assert "EVIDENCE_INCOMPLETE" in result["blockers"]


def test_review_file_is_private_and_missing_finding_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, report = _demo_report(tmp_path)
    finding = next(item for item in report["findings"] if item["status"] == "CANDIDATE")
    output = tmp_path / "review.json"
    args = ["action-review", finding["finding_id"], "--input", str(path), "--output", str(output)]
    assert main(args) == 0
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert main(args) == 2
    assert main(["action-review", "missing", "--input", str(path)]) == 2
    assert "Invalid report or finding ID" in capsys.readouterr().err


def test_table_output_escapes_control_characters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, report = _demo_report(tmp_path)
    finding = next(item for item in report["findings"] if item["status"] == "CANDIDATE")
    finding["finding_id"] = "candidate\nFAKE APPROVAL\x1b[31m"
    path.write_text(json.dumps(report), encoding="utf-8")

    assert main(["action-review", finding["finding_id"], "--input", str(path)]) == 0
    output = capsys.readouterr().out
    assert "\\nFAKE APPROVAL\\u001b" in output
    assert "\x1b" not in output
