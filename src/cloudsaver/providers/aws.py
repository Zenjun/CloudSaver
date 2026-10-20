"""AWS metadata and CloudWatch collection. No AWS write operations live here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Literal

from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
)

from cloudsaver.domain import ResourceSnapshot

REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+$")
PAGE_SIZE = 100
METRIC_DAYS = 14
IssueCategory = Literal[
    "AUTHENTICATION", "ACCESS_DENIED", "THROTTLED", "INVALID_REGION", "NETWORK", "RESPONSE"
]


@dataclass(frozen=True)
class CollectionIssue:
    scope: str
    operation: str
    category: IssueCategory
    retryable: bool
    resource_ref: str | None = None


@dataclass
class Inventory:
    observed_at: str
    account_ref: str | None = None
    resources: list[ResourceSnapshot] = field(default_factory=list)
    requested: list[str] = field(default_factory=list)
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    issues: list[CollectionIssue] = field(default_factory=list)

    @property
    def status(self) -> Literal["COMPLETE", "PARTIAL", "FAILED"]:
        if not self.failed:
            return "COMPLETE"
        metadata_completed = any(
            scope.endswith(("describe_instances", "describe_volumes", "describe_addresses"))
            for scope in self.completed
        )
        return "PARTIAL" if metadata_completed else "FAILED"

    @property
    def exit_code(self) -> int:
        if self.status == "COMPLETE":
            return 0
        if self.status == "PARTIAL":
            return 6
        if self.issues and all(issue.category == "AUTHENTICATION" for issue in self.issues):
            return 3
        if self.issues and all(issue.category == "ACCESS_DENIED" for issue in self.issues):
            return 4
        return 5


def validate_regions(regions: list[str]) -> list[str]:
    cleaned = [region.strip() for region in regions]
    if not cleaned or any(not REGION_PATTERN.fullmatch(region) for region in cleaned):
        raise ValueError("regions must be AWS region identifiers such as ap-northeast-2")
    return list(dict.fromkeys(cleaned))


def _category(error: Exception) -> tuple[IssueCategory, bool]:
    if isinstance(error, (NoCredentialsError, PartialCredentialsError, ProfileNotFound)):
        return "AUTHENTICATION", False
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
            return "ACCESS_DENIED", False
        if code in {
            "AuthFailure",
            "InvalidClientTokenId",
            "ExpiredToken",
            "UnrecognizedClientException",
        }:
            return "AUTHENTICATION", False
        if "throttl" in code.lower() or code in {
            "RequestLimitExceeded",
            "TooManyRequestsException",
        }:
            return "THROTTLED", True
        if code in {
            "RequestTimeout",
            "RequestTimeoutException",
            "ServiceUnavailable",
            "InternalError",
        }:
            return "NETWORK", True
        if code in {"InvalidRegion", "InvalidEndpoint"}:
            return "INVALID_REGION", False
    if isinstance(error, BotoCoreError):
        return "NETWORK", True
    return "RESPONSE", False


def _record_failure(
    inventory: Inventory,
    scope: str,
    operation: str,
    error: Exception,
    resource_ref: str | None = None,
) -> None:
    category, retryable = _category(error)
    inventory.failed.append(scope)
    inventory.issues.append(CollectionIssue(scope, operation, category, retryable, resource_ref))


def _tags(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("invalid AWS tags")
    if any(
        not isinstance(tag, dict)
        or not isinstance(tag.get("Key"), str)
        or not isinstance(tag.get("Value"), str)
        for tag in raw
    ):
        raise ValueError("invalid AWS tags")
    return {tag["Key"]: tag["Value"] for tag in raw}


def _snapshot(
    raw: dict[str, Any], kind: str, region: str, observed_at: str, account_ref: str | None
) -> ResourceSnapshot:
    if kind == "ec2_instance":
        resource_id = raw["InstanceId"]
        state = raw["State"]["Name"]
    elif kind == "ebs_volume":
        resource_id = raw["VolumeId"]
        state = raw["State"]
    else:
        resource_id = raw.get("AllocationId")
        if resource_id is None:
            public_ip = raw["PublicIp"]
            if not isinstance(public_ip, str):
                raise ValueError("invalid Elastic IP")
            resource_id = "eip-legacy-" + sha256(public_ip.encode("ascii")).hexdigest()[:16]
        state = "associated" if raw.get("AssociationId") else "unassociated"
    snapshot = ResourceSnapshot.from_mapping(
        {
            "resource_id": resource_id,
            "type": kind,
            "region": region,
            "tags": _tags(raw.get("Tags")),
            "state": state,
        }
    )
    return replace(snapshot, account_ref=account_ref, observed_at=observed_at)


def _pages(client: Any, operation: str, key: str) -> list[dict[str, Any]]:
    """Finish one paginated operation before exposing any of its resources."""
    result: list[dict[str, Any]] = []
    token: str | None = None
    seen: set[str] = set()
    while True:
        params: dict[str, Any] = {"MaxResults": PAGE_SIZE}
        if token is not None:
            params["NextToken"] = token
        response = getattr(client, operation)(**params)
        if operation == "describe_instances":
            for reservation in response.get("Reservations", []):
                result.extend(reservation.get("Instances", []))
        else:
            result.extend(response.get(key, []))
        token = response.get("NextToken")
        if not token:
            return result
        if token in seen:
            raise ValueError("repeated pagination token")
        seen.add(token)


def _metric(
    cloudwatch: Any, instance_id: str, end: datetime
) -> tuple[float | None, int, Literal["COMPLETE", "MISSING"]]:
    start = end - timedelta(days=METRIC_DAYS)
    params: dict[str, Any] = {
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
        "StartTime": start,
        "EndTime": end,
        "ScanBy": "TimestampAscending",
    }
    values: list[float] = []
    seen: set[str] = set()
    while True:
        response = cloudwatch.get_metric_data(**params)
        if response.get("Messages"):
            raise ValueError("CloudWatch returned operation messages")
        results = response.get("MetricDataResults", [])
        if len(results) != 1 or results[0].get("Id") != "cpu":
            raise ValueError("invalid CloudWatch result")
        result = results[0]
        if result.get("StatusCode") not in {"Complete", "PartialData"} or result.get("Messages"):
            raise ValueError("incomplete CloudWatch result")
        values.extend(float(value) for value in result.get("Values", []))
        token = response.get("NextToken")
        if not token:
            if result.get("StatusCode") == "PartialData":
                raise ValueError("incomplete CloudWatch result")
            break
        if token in seen:
            raise ValueError("repeated CloudWatch token")
        seen.add(token)
        params["NextToken"] = token
    if not values:
        return None, 0, "MISSING"
    return sum(values) / len(values), len(values), "COMPLETE"


def collect(session: Any, regions: list[str], observed_at: datetime) -> Inventory:
    """Collect only metadata and CPU observations using an injected SDK session."""
    regions = validate_regions(regions)
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    observed_at = observed_at.astimezone(UTC).replace(microsecond=0)
    inventory = Inventory(observed_at.isoformat().replace("+00:00", "Z"))
    identity_scope = "account:identity"
    inventory.requested.append(identity_scope)
    try:
        identity = session.client("sts").get_caller_identity()
        account = identity["Account"]
        if not isinstance(account, str) or not account:
            raise ValueError("missing AWS account")
        inventory.account_ref = account
        inventory.completed.append(identity_scope)
    except (BotoCoreError, ClientError, ValueError, KeyError) as error:
        _record_failure(inventory, identity_scope, "GetCallerIdentity", error)

    for region in regions:
        try:
            ec2 = session.client("ec2", region_name=region)
        except (BotoCoreError, ClientError, ValueError) as error:
            for operation in ("describe_instances", "describe_volumes", "describe_addresses"):
                scope = f"{region}:{operation}"
                inventory.requested.append(scope)
                _record_failure(inventory, scope, operation, error)
            continue
        for operation, kind, key in (
            ("describe_instances", "ec2_instance", "Reservations"),
            ("describe_volumes", "ebs_volume", "Volumes"),
            ("describe_addresses", "elastic_ip", "Addresses"),
        ):
            scope = f"{region}:{operation}"
            inventory.requested.append(scope)
            try:
                raw_items = (
                    ec2.describe_addresses().get(key, [])
                    if operation == "describe_addresses"
                    else _pages(ec2, operation, key)
                )
                snapshots = [
                    _snapshot(raw, kind, region, inventory.observed_at, inventory.account_ref)
                    for raw in raw_items
                ]
                inventory.resources.extend(snapshots)
                inventory.completed.append(scope)
            except (BotoCoreError, ClientError, ValueError, KeyError, TypeError) as error:
                _record_failure(inventory, scope, operation, error)
        running = [
            (index, resource)
            for index, resource in enumerate(inventory.resources)
            if resource.region == region
            and resource.type == "ec2_instance"
            and resource.state == "running"
        ]
        if running:
            end = observed_at.replace(hour=0, minute=0, second=0)
            try:
                cloudwatch = session.client("cloudwatch", region_name=region)
            except (BotoCoreError, ClientError, ValueError) as error:
                for index, resource in running:
                    scope = f"{region}:cloudwatch:{resource.resource_id}"
                    inventory.requested.append(scope)
                    inventory.resources[index] = replace(resource, metrics_status="ERROR")
                    _record_failure(inventory, scope, "GetMetricData", error, resource.resource_id)
                continue
            for index, resource in running:
                scope = f"{region}:cloudwatch:{resource.resource_id}"
                inventory.requested.append(scope)
                try:
                    average, count, quality = _metric(cloudwatch, resource.resource_id, end)
                    inventory.resources[index] = replace(
                        resource,
                        cpu_average=average,
                        cpu_samples=count,
                        period_start=(end - timedelta(days=METRIC_DAYS))
                        .isoformat()
                        .replace("+00:00", "Z"),
                        period_end=end.isoformat().replace("+00:00", "Z"),
                        metrics_status=quality,
                    )
                    inventory.completed.append(scope)
                except (BotoCoreError, ClientError, ValueError, KeyError, TypeError) as error:
                    inventory.resources[index] = replace(resource, metrics_status="ERROR")
                    _record_failure(inventory, scope, "GetMetricData", error, resource.resource_id)
    inventory.resources.sort(
        key=lambda resource: (resource.region, resource.type, resource.resource_id)
    )
    return inventory


def new_session(profile: str | None, regions: list[str]) -> Any:
    """Create SDK clients only for the explicit AWS scan command."""
    import boto3

    config = Config(
        retries={"mode": "standard", "total_max_attempts": 3},
        connect_timeout=5,
        read_timeout=15,
    )
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    available = set().union(
        *(
            session.get_available_regions("ec2", partition_name=partition)
            for partition in ("aws", "aws-us-gov", "aws-cn")
        )
    )
    if any(region not in available for region in regions):
        raise ValueError("unsupported AWS region; update boto3/botocore if it is new")
    if session.get_credentials() is None:
        raise NoCredentialsError()
    return ConfiguredSession(session, config)


class ConfiguredSession:
    def __init__(self, session: Any, config: Config) -> None:
        self.session = session
        self.config = config

    def client(self, service: str, *, region_name: str | None = None) -> Any:
        return self.session.client(service, region_name=region_name, config=self.config)
