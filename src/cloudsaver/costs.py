"""Offline arithmetic for explicitly supplied monthly cost scenarios."""

import re
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from cloudsaver.domain import SavingsEstimate

MONEY = Decimal("0.01")
COMPONENTS = {
    "low_utilization_ec2": {"compute", "ebs", "ipv4"},
    "unattached_ebs": {"ebs"},
    "potential_unused_public_ipv4": {"ipv4"},
}


def _money(value: Any) -> Decimal:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value) is None:
        raise ValueError("cost amounts must be decimal strings")
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid cost amount") from error
    if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999.99"):
        raise ValueError("cost amount is out of range")
    if amount != amount.quantize(MONEY):
        raise ValueError("cost amounts must be nonnegative with at most two decimal places")
    return amount


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("cost source timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid cost source timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("cost source timestamp must include a timezone")
    return value


def calculate(policy_id: str, scenario: dict[str, Any]) -> SavingsEstimate:
    """Calculate a conditional estimate; supplied costs are never treated as a bill."""
    expected = COMPONENTS.get(policy_id)
    if expected is None:
        raise ValueError("unsupported cost policy")
    region = scenario.get("region")
    if (
        not isinstance(region, str)
        or re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-[0-9]+", region) is None
    ):
        raise ValueError("cost scenario requires an AWS region")
    currency = scenario.get("currency")
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or re.fullmatch(r"[A-Z]{3}", currency) is None
    ):
        raise ValueError("currency must be a three-letter uppercase code")
    source = scenario.get("source")
    if not isinstance(source, str) or source not in {"AWS_PRICING", "AWS_COST_EXPORT"}:
        raise ValueError("cost source must identify AWS Pricing or an AWS cost export")
    as_of = _timestamp(scenario.get("as_of"))
    raw_components = scenario.get("components")
    if not isinstance(raw_components, list) or len(raw_components) != len(expected):
        raise ValueError("all required cost components must be supplied")
    seen: set[str] = set()
    baseline = Decimal("0")
    optimized = Decimal("0")
    for component in raw_components:
        if not isinstance(component, dict):
            raise ValueError("invalid cost component")
        kind = component.get("kind")
        if not isinstance(kind, str) or kind not in expected or kind in seen:
            raise ValueError("unexpected or duplicate cost component")
        seen.add(kind)
        before = _money(component.get("baseline"))
        after = _money(component.get("optimized"))
        if after > before:
            raise ValueError("optimized cost cannot exceed baseline in a savings scenario")
        if kind == "compute" and after != 0:
            raise ValueError("EC2 stop scenario must remove compute cost")
        if policy_id == "low_utilization_ec2" and kind in {"ebs", "ipv4"} and after != before:
            raise ValueError("EC2 stop scenario must retain EBS and IPv4 costs")
        if policy_id != "low_utilization_ec2" and after != 0:
            raise ValueError("release scenario must remove the selected resource cost")
        baseline += before
        optimized += after
    if seen != expected:
        raise ValueError("all required cost components must be supplied")
    assumptions = [
        "User-supplied monthly cost components; source and billing applicability are unverified.",
        f"Amounts are supplied for region {region}; regional price selection is unverified.",
        "This is a hypothetical change, not an observed or verified saving.",
        "Savings Plans, Reserved Instances, free tier, credits, regional pricing and billing "
        "lag may change the result.",
        "Cost Explorer resource attribution may not match these components.",
    ]
    excluded = [
        "Taxes, data transfer, snapshots, and other unlisted charges are excluded.",
    ]
    if policy_id == "low_utilization_ec2":
        assumptions.append("EC2 compute charge becomes zero; EBS and public IPv4 charges continue.")
    if policy_id == "unattached_ebs":
        assumptions.append(
            "Volume removal is hypothetical; data retention and snapshot needs require review."
        )
    if policy_id == "potential_unused_public_ipv4":
        assumptions.append(
            "Address release is hypothetical; future allocation needs require review."
        )
    return SavingsEstimate(
        currency=currency,
        baseline=f"{baseline:.2f}",
        optimized=f"{optimized:.2f}",
        potential_savings=f"{baseline - optimized:.2f}",
        confidence="CONDITIONAL",
        formula="sum(components.baseline) - sum(components.optimized)",
        assumptions=assumptions,
        excluded_costs=excluded,
        data_sources=[f"{source} (user supplied, as of {as_of})"],
    )


def apply_scenarios(document: dict[str, Any], cost_input: dict[str, Any]) -> dict[str, Any]:
    """Enrich candidate findings only; unknowns and exclusions retain UNKNOWN values."""
    if cost_input.get("schema_version") != "1.0.0":
        raise ValueError("unsupported cost input schema")
    scenarios = cost_input.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("cost scenarios must be a list")
    enriched = deepcopy(document)
    findings = enriched["findings"]
    by_id = {item["finding_id"]: item for item in findings}
    seen: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            raise ValueError("invalid cost scenario")
        finding_id = scenario.get("finding_id")
        if not isinstance(finding_id, str) or finding_id in seen or finding_id not in by_id:
            raise ValueError("unknown or duplicate cost finding ID")
        seen.add(finding_id)
        finding = by_id[finding_id]
        if finding["status"] != "CANDIDATE":
            raise ValueError("cost scenarios are accepted only for candidates")
        parts = finding_id.split(":", 3)
        if len(parts) != 4 or scenario.get("region") != parts[2]:
            raise ValueError("cost region does not match the finding")
        finding["savings"] = asdict(calculate(finding["policy_id"], scenario))
    return enriched
