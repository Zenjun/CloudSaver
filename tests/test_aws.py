"""All AWS responses are local Stubber fixtures; these tests use no account."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pytest
from botocore.exceptions import ConnectTimeoutError, NoCredentialsError
from botocore.stub import Stubber

from cloudsaver.cli import main
from cloudsaver.providers.aws import (
    CollectionIssue,
    Inventory,
    collect,
    new_session,
    validate_regions,
)
from cloudsaver.report import inventory_document

NOW = datetime(2026, 10, 19, tzinfo=UTC)
REGION = "ap-northeast-2"


class FakeSession:
    def __init__(self) -> None:
        session = boto3.Session(
            aws_access_key_id="stub-key",
            aws_secret_access_key="stub-secret",
            region_name=REGION,
        )
        self.sts = session.client("sts")
        self.ec2 = session.client("ec2", region_name=REGION)
        self.cloudwatch = session.client("cloudwatch", region_name=REGION)

    def client(self, service: str, *, region_name: str | None = None) -> Any:
        assert region_name is None or region_name == REGION
        return {"sts": self.sts, "ec2": self.ec2, "cloudwatch": self.cloudwatch}[service]


def _identity(stubber: Stubber) -> None:
    stubber.add_response(
        "get_caller_identity",
        {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test/session",
            "UserId": "test",
        },
        {},
    )


def _metric_params(instance_id: str, token: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "MetricDataQueries": [
            {
                "Id": "cpu",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                    },
                    "Period": 86400,
                    "Stat": "Average",
                },
                "ReturnData": True,
            }
        ],
        "StartTime": NOW - timedelta(days=14),
        "EndTime": NOW,
        "ScanBy": "TimestampAscending",
    }
    if token:
        result["NextToken"] = token
    return result


def test_paginated_resources_and_metrics_are_complete_and_redacted() -> None:
    session = FakeSession()
    with (
        Stubber(session.sts) as sts,
        Stubber(session.ec2) as ec2,
        Stubber(session.cloudwatch) as cloudwatch,
    ):
        _identity(sts)
        ec2.add_response(
            "describe_instances",
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-one",
                                "State": {"Name": "running"},
                                "Tags": [{"Key": "secret-tag", "Value": "sensitive-value"}],
                            }
                        ]
                    }
                ],
                "NextToken": "i-next",
            },
            {"MaxResults": 100},
        )
        ec2.add_response(
            "describe_instances",
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-two", "State": {"Name": "stopped"}}]}
                ]
            },
            {"MaxResults": 100, "NextToken": "i-next"},
        )
        ec2.add_response(
            "describe_volumes",
            {"Volumes": [{"VolumeId": "vol-one", "State": "available"}], "NextToken": "v-next"},
            {"MaxResults": 100},
        )
        ec2.add_response(
            "describe_volumes", {"Volumes": []}, {"MaxResults": 100, "NextToken": "v-next"}
        )
        ec2.add_response(
            "describe_addresses",
            {"Addresses": [{"AllocationId": "eipalloc-one", "PublicIp": "198.51.100.10"}]},
            {},
        )
        cloudwatch.add_response(
            "get_metric_data",
            {
                "MetricDataResults": [{"Id": "cpu", "StatusCode": "PartialData", "Values": [1.0]}],
                "NextToken": "m-next",
            },
            _metric_params("i-one"),
        )
        cloudwatch.add_response(
            "get_metric_data",
            {"MetricDataResults": [{"Id": "cpu", "StatusCode": "Complete", "Values": [3.0]}]},
            _metric_params("i-one", "m-next"),
        )
        inventory = collect(session, [REGION], NOW)
        sts.assert_no_pending_responses()
        ec2.assert_no_pending_responses()
        cloudwatch.assert_no_pending_responses()
    assert inventory.status == "COMPLETE"
    assert inventory.exit_code == 0
    assert len(inventory.resources) == 4
    first = next(item for item in inventory.resources if item.resource_id == "i-one")
    assert first.cpu_average == 2.0 and first.cpu_samples == 2
    assert first.metrics_status == "COMPLETE"
    stopped = next(item for item in inventory.resources if item.resource_id == "i-two")
    assert stopped.metrics_status == "NOT_REQUESTED"
    public = json.dumps(inventory_document(inventory))
    assert "123456789012" not in public
    assert "sensitive-value" not in public
    assert "198.51.100.10" not in public
    assert '"analysis_status": "NOT_EVALUATED"' in public


def test_missing_metric_is_not_zero() -> None:
    session = FakeSession()
    with (
        Stubber(session.sts) as sts,
        Stubber(session.ec2) as ec2,
        Stubber(session.cloudwatch) as cloudwatch,
    ):
        _identity(sts)
        ec2.add_response(
            "describe_instances",
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-empty", "State": {"Name": "running"}}]}
                ]
            },
            {"MaxResults": 100},
        )
        ec2.add_response("describe_volumes", {"Volumes": []}, {"MaxResults": 100})
        ec2.add_response("describe_addresses", {"Addresses": []}, {})
        cloudwatch.add_response(
            "get_metric_data",
            {"MetricDataResults": [{"Id": "cpu", "StatusCode": "Complete", "Values": []}]},
            _metric_params("i-empty"),
        )
        inventory = collect(session, [REGION], NOW)
    assert inventory.status == "COMPLETE"
    assert inventory.resources[0].cpu_average is None
    assert inventory.resources[0].cpu_samples == 0
    assert inventory.resources[0].metrics_status == "MISSING"


def test_access_denied_and_mid_pagination_error_never_look_like_zero_resources() -> None:
    session = FakeSession()
    with Stubber(session.sts) as sts, Stubber(session.ec2) as ec2:
        _identity(sts)
        ec2.add_response(
            "describe_instances",
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-partial", "State": {"Name": "stopped"}}]}
                ],
                "NextToken": "next",
            },
            {"MaxResults": 100},
        )
        ec2.add_client_error(
            "describe_instances",
            service_error_code="RequestLimitExceeded",
            expected_params={"MaxResults": 100, "NextToken": "next"},
        )
        ec2.add_client_error(
            "describe_volumes",
            service_error_code="UnauthorizedOperation",
            expected_params={"MaxResults": 100},
        )
        ec2.add_response("describe_addresses", {"Addresses": []}, {})
        inventory = collect(session, [REGION], NOW)
    assert inventory.status == "PARTIAL"
    assert inventory.exit_code == 6
    assert inventory.resources == []  # the first instance page was discarded
    assert len(inventory.failed) == 2
    assert {issue.category for issue in inventory.issues} == {"THROTTLED", "ACCESS_DENIED"}
    assert inventory_document(inventory)["scope"]["failed"]


def test_all_metadata_failures_are_failed_even_if_identity_succeeds() -> None:
    session = FakeSession()
    with Stubber(session.sts) as sts, Stubber(session.ec2) as ec2:
        _identity(sts)
        for operation, params in (
            ("describe_instances", {"MaxResults": 100}),
            ("describe_volumes", {"MaxResults": 100}),
            ("describe_addresses", {}),
        ):
            ec2.add_client_error(
                operation, service_error_code="UnauthorizedOperation", expected_params=params
            )
        inventory = collect(session, [REGION], NOW)
    assert inventory.status == "FAILED"
    assert inventory.exit_code == 4
    assert inventory.resources == []


def test_cli_rejects_regions_and_reports_missing_credentials(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert validate_regions([REGION, REGION]) == [REGION]
    assert main(["scan", "--regions", "bad-region"]) == 2
    assert "regions" in capsys.readouterr().err

    def unavailable(_profile: str | None, _regions: list[str]) -> None:
        raise NoCredentialsError()

    monkeypatch.setattr("cloudsaver.providers.aws.new_session", unavailable)
    assert main(["scan", "--regions", REGION]) == 3
    assert "credentials" in capsys.readouterr().err


def test_timeout_category_is_retryable_without_raw_exception_text() -> None:
    from cloudsaver.providers.aws import _category

    category, retryable = _category(ConnectTimeoutError(endpoint_url="https://example.invalid"))
    assert category == "NETWORK" and retryable


def test_cli_emits_partial_json_and_exit_six(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    inventory = Inventory(
        observed_at="2026-10-19T00:00:00Z",
        requested=["account:identity", f"{REGION}:describe_volumes"],
        completed=[f"{REGION}:describe_volumes"],
        failed=["account:identity"],
        issues=[CollectionIssue("account:identity", "GetCallerIdentity", "NETWORK", True)],
    )
    monkeypatch.setattr("cloudsaver.providers.aws.new_session", lambda *_args: object())
    monkeypatch.setattr("cloudsaver.providers.aws.collect", lambda *_args: inventory)
    assert main(["scan", "--regions", REGION, "--format", "json"]) == 6
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "PARTIAL"
    assert result["scope"]["failed"] == ["account:identity"]
    assert result["collection_issues"][0]["category"] == "NETWORK"


def test_legacy_elastic_ip_uses_non_ip_reference() -> None:
    from cloudsaver.providers.aws import _snapshot

    snapshot = _snapshot(
        {"PublicIp": "198.51.100.42"}, "elastic_ip", REGION, "2026-10-19T00:00:00Z", None
    )
    assert snapshot.resource_id.startswith("eip-legacy-")
    assert "198.51.100.42" not in snapshot.resource_id


def test_cloudwatch_denial_preserves_instance_with_error_quality() -> None:
    session = FakeSession()
    with (
        Stubber(session.sts) as sts,
        Stubber(session.ec2) as ec2,
        Stubber(session.cloudwatch) as cloudwatch,
    ):
        _identity(sts)
        ec2.add_response(
            "describe_instances",
            {
                "Reservations": [
                    {"Instances": [{"InstanceId": "i-denied", "State": {"Name": "running"}}]}
                ]
            },
            {"MaxResults": 100},
        )
        ec2.add_response("describe_volumes", {"Volumes": []}, {"MaxResults": 100})
        ec2.add_response("describe_addresses", {"Addresses": []}, {})
        cloudwatch.add_client_error(
            "get_metric_data",
            service_error_code="AccessDenied",
            expected_params=_metric_params("i-denied"),
        )
        inventory = collect(session, [REGION], NOW)
    assert inventory.status == "PARTIAL"
    assert inventory.resources[0].cpu_average is None
    assert inventory.resources[0].metrics_status == "ERROR"
    assert inventory.issues[0].category == "ACCESS_DENIED"


def test_session_uses_standard_bounded_retries_without_api_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class SDKSession:
        def get_available_regions(self, _service: str, *, partition_name: str) -> list[str]:
            return [REGION] if partition_name == "aws" else []

        def get_credentials(self) -> object:
            return object()

        def client(self, _service: str, *, region_name: str | None, config: Any) -> Any:
            assert region_name == REGION
            assert config.retries["mode"] == "standard"
            assert config.retries["total_max_attempts"] == 3
            assert config.connect_timeout == 5
            assert config.read_timeout == 15
            return object()

    monkeypatch.setattr(boto3, "Session", lambda **_kwargs: SDKSession())
    session = new_session(None, [REGION])
    session.client("ec2", region_name=REGION)
    with pytest.raises(ValueError, match="unsupported AWS region"):
        new_session(None, ["us-east-99"])
