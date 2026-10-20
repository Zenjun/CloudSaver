"""The optional dashboard reads saved data and never changes cloud resources."""

import json
import stat
from pathlib import Path

from cloudsaver.cli import main
from cloudsaver.demo import scan
from cloudsaver.report import document


def _saved_demo(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    observed_at, findings = scan()
    data = document(observed_at, findings)
    path = tmp_path / "demo.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def test_dashboard_shows_distinct_statuses_and_explanations(tmp_path: Path) -> None:
    source, _ = _saved_demo(tmp_path)
    output = tmp_path / "dashboard.html"

    assert main(["dashboard", "--input", str(source), "--output", str(output)]) == 0
    page = output.read_text(encoding="utf-8")

    assert "DEMO DATA" in page
    assert "CANDIDATE" in page
    assert "EXCLUDED" in page
    assert "INSUFFICIENT_DATA" in page
    assert "금액 미확인" in page
    assert "CPUUtilization.average" in page
    assert "수집 범위와 문제" in page
    assert "default-src 'none'" in page
    assert "<script" not in page
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_dashboard_escapes_untrusted_report_text(tmp_path: Path) -> None:
    source, report = _saved_demo(tmp_path)
    findings = report["findings"]
    assert isinstance(findings, list)
    findings[0]["explanation"] = '<script>alert("bad")</script>'
    findings[0]["risk"]["reasons"] = ['<img src=x onerror="bad()">']
    source.write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "dashboard.html"

    assert main(["dashboard", "--input", str(source), "--output", str(output)]) == 0
    page = output.read_text(encoding="utf-8")
    assert "<script>" not in page
    assert "<img src=x" not in page
    assert "&lt;script&gt;" in page
    assert "&lt;img src=x" in page


def test_dashboard_refuses_invalid_input_and_existing_output(tmp_path: Path) -> None:
    source, _ = _saved_demo(tmp_path)
    output = tmp_path / "dashboard.html"
    output.write_text("keep", encoding="utf-8")

    assert main(["dashboard", "--input", str(source), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "keep"

    source.write_text("{}", encoding="utf-8")
    assert main(["dashboard", "--input", str(source), "--output", str(tmp_path / "new.html")]) == 2
    assert not (tmp_path / "new.html").exists()


def test_dashboard_preserves_partial_aws_collection_state(tmp_path: Path) -> None:
    source, report = _saved_demo(tmp_path)
    report.update(
        {
            "data_kind": "AWS",
            "status": "PARTIAL",
            "analysis_status": "PARTIAL",
            "account_ref": "REDACTED",
            "resources": [],
            "scope": {
                "requested": ["ap-northeast-2:ec2", "ap-northeast-2:cloudwatch"],
                "completed": ["ap-northeast-2:ec2"],
                "failed": ["ap-northeast-2:cloudwatch"],
            },
            "collection_issues": [
                {
                    "scope": "ap-northeast-2:cloudwatch",
                    "operation": "GetMetricData",
                    "category": "ACCESS_DENIED",
                    "retryable": False,
                    "resource_ref": None,
                }
            ],
        }
    )
    source.write_text(json.dumps(report), encoding="utf-8")
    output = tmp_path / "partial.html"

    assert main(["dashboard", "--input", str(source), "--output", str(output)]) == 0
    page = output.read_text(encoding="utf-8")
    assert "분석 상태: PARTIAL" in page
    assert "ACCESS_DENIED" in page
    assert "ap-northeast-2:cloudwatch" in page
    assert "DEMO DATA" not in page


def test_dashboard_uses_existing_conditional_cost_engine(tmp_path: Path) -> None:
    source, report = _saved_demo(tmp_path)
    finding = next(
        item
        for item in report["findings"]
        if item["policy_id"] == "unattached_ebs" and item["status"] == "CANDIDATE"
    )
    costs = tmp_path / "costs.json"
    costs.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "scenarios": [
                    {
                        "finding_id": finding["finding_id"],
                        "currency": "USD",
                        "region": "ap-northeast-2",
                        "source": "AWS_PRICING",
                        "as_of": "2026-10-01T00:00:00Z",
                        "components": [{"kind": "ebs", "baseline": "5.25", "optimized": "0.00"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "priced.html"

    assert (
        main(
            [
                "dashboard",
                "--input",
                str(source),
                "--cost-input",
                str(costs),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    page = output.read_text(encoding="utf-8")
    assert "5.25 USD / 월" in page
    assert "CONDITIONAL" in page
    assert "금액 미확인" in page
