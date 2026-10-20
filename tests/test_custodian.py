"""Phase 5 policy boundary and local Custodian adapter tests."""

import json
import subprocess
from pathlib import Path

import pytest

from cloudsaver import custodian
from cloudsaver.cli import main

SAFE = """policies:
  - name: detached-ebs
    resource: aws.ebs
    filters:
      - type: value
        key: State
        value: available
"""
ROLE = "arn:aws:iam::123456789012:role/CloudSaverReadOnly"


def policy_file(tmp_path: Path, content: str = SAFE) -> Path:
    path = tmp_path / "policy.yml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "content",
    [
        SAFE + "    actions: []\n",
        SAFE + "    mode: {}\n",
        SAFE.replace("type: value", "type: invoke-lambda"),
        SAFE.replace("key: State", "key: value_from"),
        SAFE.replace("resource: aws.ebs", "resource: aws.lambda"),
        SAFE.replace("resource: aws.ebs", "resource: [aws.ebs]"),
        SAFE.replace("key: State", "key: [State]"),
        SAFE.replace("value: available", "value: available\n        value: in-use"),
        SAFE + "  - name: detached-ebs\n    resource: aws.ebs\n    filters: []\n",
    ],
)
def test_unsafe_policy_rejected_before_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    def forbidden() -> Path:
        raise AssertionError("Custodian must not start")

    monkeypatch.setattr(custodian, "_binary", forbidden)
    with pytest.raises(ValueError):
        custodian.run(policy_file(tmp_path, content), evaluate=False)


def test_validation_uses_sanitized_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(custodian, "_binary", lambda: Path("/fake/custodian"))
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        clean = Path(command[-1]).read_text(encoding="utf-8")
        assert "actions" not in clean
        assert "mode" not in clean
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(custodian.subprocess, "run", fake_run)
    result = custodian.run(policy_file(tmp_path), evaluate=False)
    assert result["data_kind"] == "CUSTODIAN"
    assert result["evaluation_status"] == "NOT_EVALUATED"
    assert [command[1] for command in commands] == ["validate"]


def test_evaluation_has_iam_boundary_and_redacted_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(custodian, "_binary", lambda: Path("/fake/custodian"))
    commands: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[1] == "run":
            output = Path(command[command.index("-s") + 1])
            match = output / "detached-ebs" / "resources.json"
            match.parent.mkdir(parents=True)
            match.write_text(
                json.dumps(
                    [
                        {
                            "VolumeId": "vol-12345678",
                            "Tags": [{"Value": "SECRET"}],
                            "PublicIp": "1.2.3.4",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            access = json.loads(Path(command[command.index("--session-policy") + 1]).read_text())
            assert all(
                "Describe" in action or action == "sts:GetCallerIdentity"
                for action in access["Statement"][0]["Action"]
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(custodian.subprocess, "run", fake_run)
    result = custodian.run(
        policy_file(tmp_path), evaluate=True, region="ap-northeast-2", assume_role=ROLE
    )
    assert [command[1] for command in commands] == ["validate", "run"]
    assert "--dryrun" in commands[1]
    assert "--assume" in commands[1]
    assert commands[1][commands[1].index("--assume") + 1] == ROLE
    assert "--cache" in commands[1]
    assert result["policy_results"][0]["matched_count"] == 1
    assert result["policy_results"][0]["resource_refs"] == ["vol-12345678"]
    assert "SECRET" not in json.dumps(result)
    assert "1.2.3.4" not in json.dumps(result)
    assert ROLE not in json.dumps(result)


def test_evaluation_requires_role_before_custodian(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(custodian, "_binary", lambda: pytest.fail("must not start"))
    with pytest.raises(ValueError):
        custodian.run(policy_file(tmp_path), evaluate=True, region="ap-northeast-2")


def test_missing_custodian_output_is_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(custodian, "_binary", lambda: Path("/fake/custodian"))
    monkeypatch.setattr(
        custodian.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    with pytest.raises(custodian.CustodianFailure):
        custodian.run(
            policy_file(tmp_path), evaluate=True, region="ap-northeast-2", assume_role=ROLE
        )


def test_custodian_failure_is_not_zero_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(custodian, "_binary", lambda: Path("/fake/custodian"))

    def failed(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "SECRET", "AccessDenied: SECRET")

    monkeypatch.setattr(custodian.subprocess, "run", failed)
    code = main(["custodian", "validate", "--policy", str(policy_file(tmp_path))])
    assert code == 5
    output = capsys.readouterr()
    assert "SECRET" not in output.out + output.err


def test_malformed_resource_reference_is_not_disclosed() -> None:
    refs = custodian._resource_refs([{"VolumeId": "vol-123 SECRET"}], "aws.ebs")
    assert refs == []
