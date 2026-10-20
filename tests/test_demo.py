import json
import os
import socket
from pathlib import Path

import pytest

from cloudsaver.cli import main
from cloudsaver.demo import scan
from cloudsaver.report import document


def test_fixture_covers_candidate_protection_and_missing_data() -> None:
    observed_at, findings = scan()
    report = document(observed_at, findings)
    assert report["schema_version"] == "1.1.0"
    assert report["notice"] == "DEMO DATA"
    assert report["scope"]["failed"] == []
    assert len(findings) == 5
    by_ref = {finding.resource_ref: finding for finding in findings}
    assert by_ref["i-demo-dev"].status == "CANDIDATE"
    assert by_ref["i-demo-prod"].status == "EXCLUDED"
    assert by_ref["i-demo-prod"].risk.level == "CRITICAL"
    assert by_ref["vol-demo-unattached"].risk.level == "UNKNOWN"
    assert "data_retention" in by_ref["vol-demo-unattached"].risk.unknown_factors
    assert by_ref["eipalloc-demo-unused"].policy_id == "potential_unused_public_ipv4"
    assert by_ref["i-demo-no-metrics"].status == "INSUFFICIENT_DATA"
    assert by_ref["i-demo-no-metrics"].evidence[0].value is None
    assert all(finding.savings.potential_savings == "UNKNOWN" for finding in findings)


def test_json_is_deterministic_and_does_not_expose_tags_or_credentials(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["demo", "scan", "--format", "json"]) == 0
    first = capsys.readouterr().out
    assert main(["demo", "scan", "--format", "json"]) == 0
    second = capsys.readouterr().out
    assert first == second
    parsed = json.loads(first)
    assert parsed["data_kind"] == "DEMO"
    assert parsed["status"] == "COMPLETE"
    assert '"tags"' not in first
    assert "AWS_SECRET_ACCESS_KEY" not in first


def test_demo_never_opens_network_even_with_no_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access in demo mode")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    assert main(["demo", "scan"]) == 0
    assert "DEMO DATA" in capsys.readouterr().out


def test_output_file_is_private_and_existing_file_is_preserved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "report.json"
    assert main(["demo", "scan", "--format", "json", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["notice"] == "DEMO DATA"
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert main(["demo", "scan", "--format", "json", "--output", str(output)]) == 2
    assert json.loads(output.read_text())["notice"] == "DEMO DATA"
    assert "already exists" in capsys.readouterr().err


def test_cli_help_and_invalid_options_have_expected_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    assert "demo" in capsys.readouterr().out
    with pytest.raises(SystemExit) as invalid_exit:
        main(["demo", "scan", "--format", "xml"])
    assert invalid_exit.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
