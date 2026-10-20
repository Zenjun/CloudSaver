"""Narrow Cloud Custodian adapter. The evaluation path always assumes a constrained role."""

import json
import re
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

RESOURCE_IDS = {
    "aws.ec2": "InstanceId",
    "aws.ebs": "VolumeId",
    "aws.elastic-ip": "AllocationId",
}
FILTER_KEYS = {
    "aws.ec2": {"State.Name"},
    "aws.ebs": {"State"},
    "aws.elastic-ip": {"AssociationId"},
}
SESSION_ACTIONS = [
    "ec2:DescribeAddresses",
    "ec2:DescribeInstances",
    "ec2:DescribeRegions",
    "ec2:DescribeTags",
    "ec2:DescribeVolumes",
    "sts:GetCallerIdentity",
]
ROLE_PATTERN = re.compile(r"^arn:(?:aws|aws-us-gov|aws-cn):iam::[0-9]{12}:role/[\w+=,.@/-]+$")
REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+$")
POLICY_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
VERSION = "0.9.53"


class CustodianUnavailable(Exception):
    pass


class CustodianFailure(Exception):
    pass


def _loader() -> Any:
    try:
        import yaml
    except ImportError as error:
        raise CustodianUnavailable("Cloud Custodian support is not installed.") from error

    class StrictLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader: Any, node: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str) or key in result:
                raise ValueError("duplicate or non-string policy key")
            result[key] = loader.construct_object(value_node)
        return result

    StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return yaml, StrictLoader


def load_policy(path: Path) -> dict[str, Any]:
    """Parse only a small action-free pull-policy subset and rebuild it from validated fields."""
    yaml, loader = _loader()
    if path.stat().st_size > 1_000_000:
        raise ValueError("policy file is too large")
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
    except (yaml.YAMLError, UnicodeError) as error:
        raise ValueError("invalid policy YAML") from error
    if not isinstance(raw, dict) or set(raw) != {"policies"}:
        raise ValueError("policy must contain only a policies list")
    raw_policies = raw["policies"]
    if not isinstance(raw_policies, list) or not 1 <= len(raw_policies) <= 10:
        raise ValueError("policy list must contain 1 to 10 entries")
    policies = []
    names: set[str] = set()
    for item in raw_policies:
        if not isinstance(item, dict):
            raise ValueError("invalid policy")
        if "actions" in item or "mode" in item:
            raise ValueError("actions and execution modes are prohibited")
        if set(item) - {"name", "resource", "filters", "description"}:
            raise ValueError("unsupported policy field")
        name = item.get("name")
        resource = item.get("resource")
        filters = item.get("filters")
        if not isinstance(name, str) or not POLICY_PATTERN.fullmatch(name) or name in names:
            raise ValueError("invalid or duplicate policy name")
        names.add(name)
        if not isinstance(resource, str) or resource not in RESOURCE_IDS:
            raise ValueError("unsupported policy resource")
        if not isinstance(filters, list) or not 1 <= len(filters) <= 10:
            raise ValueError("policy requires 1 to 10 safe filters")
        clean_filters = []
        for condition in filters:
            if not isinstance(condition, dict) or set(condition) - {"type", "key", "value", "op"}:
                raise ValueError("unsupported filter")
            if condition.get("type") != "value" or condition.get("op", "eq") != "eq":
                raise ValueError("only equality value filters are supported")
            key = condition.get("key")
            value = condition.get("value")
            if not isinstance(key, str) or key not in FILTER_KEYS[resource]:
                raise ValueError("unsupported filter key")
            if (
                not isinstance(value, (str, int, bool))
                or isinstance(value, str)
                and len(value) > 128
            ):
                raise ValueError("invalid filter value")
            clean_filters.append({"type": "value", "key": key, "value": value, "op": "eq"})
        clean: dict[str, Any] = {"name": name, "resource": resource, "filters": clean_filters}
        description = item.get("description")
        if description is not None:
            if not isinstance(description, str) or len(description) > 500:
                raise ValueError("invalid policy description")
            clean["description"] = description
        policies.append(clean)
    return {"policies": policies}


def _binary() -> Path:
    try:
        installed = version("c7n")
    except PackageNotFoundError as error:
        raise CustodianUnavailable("Install cloudsaver[custodian].") from error
    if installed != VERSION:
        raise CustodianUnavailable("Unsupported Cloud Custodian version.")
    binary = Path(sys.executable).with_name("custodian")
    if not binary.is_file():
        raise CustodianUnavailable("Cloud Custodian executable is unavailable.")
    return binary


def session_policy() -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": SESSION_ACTIONS, "Resource": "*"}],
    }


def _invoke(command: list[str], *, timeout: int) -> None:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise CustodianFailure("Cloud Custodian did not complete.") from error
    if result.returncode != 0:
        raise CustodianFailure("Cloud Custodian command failed.")


def _resource_refs(resources: list[Any], resource_type: str) -> list[str]:
    key = RESOURCE_IDS[resource_type]
    prefix = {"aws.ec2": "i", "aws.ebs": "vol", "aws.elastic-ip": "eipalloc"}[resource_type]
    refs = []
    for resource in resources:
        if not isinstance(resource, dict):
            raise CustodianFailure("Invalid Cloud Custodian output.")
        identifier = resource.get(key)
        if isinstance(identifier, str) and re.fullmatch(
            rf"{prefix}-[0-9a-f]{{8}}(?:[0-9a-f]{{9}})?", identifier
        ):
            refs.append(identifier)
    return sorted(refs)


def run(
    policy_path: Path,
    *,
    evaluate: bool,
    region: str | None = None,
    assume_role: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    policy = load_policy(policy_path)
    if evaluate and (
        not isinstance(region, str)
        or not REGION_PATTERN.fullmatch(region)
        or not isinstance(assume_role, str)
        or not ROLE_PATTERN.fullmatch(assume_role)
    ):
        raise ValueError("evaluation requires a region and an IAM role ARN")
    binary = _binary()
    with TemporaryDirectory(prefix="cloudsaver-c7n-") as temp:
        workspace = Path(temp)
        yaml, _ = _loader()
        safe_path = workspace / "policy.yml"
        safe_path.write_text(yaml.safe_dump(policy, sort_keys=True), encoding="utf-8")
        _invoke([str(binary), "validate", str(safe_path)], timeout=30)
        result: dict[str, Any] = {
            "schema_version": "1.0.0",
            "data_kind": "CUSTODIAN",
            "validation_status": "VALID",
            "evaluation_status": "NOT_EVALUATED",
            "policy_results": [
                {"name": item["name"], "resource": item["resource"]} for item in policy["policies"]
            ],
        }
        if not evaluate:
            return result
        assert region is not None and assume_role is not None
        access_path = workspace / "session-policy.json"
        access_path.write_text(json.dumps(session_policy()), encoding="utf-8")
        output = workspace / "matches"
        command = [
            str(binary),
            "run",
            "--dryrun",
            "--region",
            region,
            "--assume",
            assume_role,
            "--session-policy",
            str(access_path),
            "--cache",
            str(workspace / "cache"),
            "-s",
            str(output),
        ]
        if profile:
            command.extend(["--profile", profile])
        command.append(str(safe_path))
        _invoke(command, timeout=120)
        for item in result["policy_results"]:
            try:
                matches = list(output.rglob(f"{item['name']}/resources.json"))
                if len(matches) != 1 or matches[0].stat().st_size > 50_000_000:
                    raise CustodianFailure("Cloud Custodian output is missing or too large.")
                resources = json.loads(matches[0].read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise CustodianFailure("Invalid Cloud Custodian output.") from error
            if not isinstance(resources, list):
                raise CustodianFailure("Invalid Cloud Custodian output.")
            item["matched_count"] = len(resources)
            item["resource_refs"] = _resource_refs(resources, item["resource"])
        result["evaluation_status"] = "COMPLETE"
        result["region"] = region
        return result
