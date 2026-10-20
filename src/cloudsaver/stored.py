"""Validated, redacted views of reports written by CloudSaver."""

import json
from math import isfinite
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1.0"
SUPPORTED_VERSIONS = {"1.0.0", SCHEMA_VERSION}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("invalid report string list")
    return value


def _optional_string(value: Any) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("invalid optional report text")
    return value


def _finding(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("invalid finding")
    for key in ("finding_id", "policy_id", "status", "explanation"):
        if not isinstance(raw.get(key), str):
            raise ValueError("invalid finding field")
    if raw["status"] not in ("CANDIDATE", "EXCLUDED", "INSUFFICIENT_DATA"):
        raise ValueError("invalid finding status")
    resource = raw.get("resource")
    risk = raw.get("risk")
    savings = raw.get("savings")
    evidence = raw.get("evidence")
    if not isinstance(resource, dict) or not all(
        isinstance(resource.get(key), str) for key in ("type", "ref")
    ):
        raise ValueError("invalid finding resource")
    if not isinstance(risk, dict) or risk.get("level") not in (
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        "UNKNOWN",
    ):
        raise ValueError("invalid finding risk")
    if not isinstance(savings, dict):
        raise ValueError("invalid finding savings")
    if not isinstance(evidence, list):
        raise ValueError("invalid finding evidence")
    clean_evidence = []
    for item in evidence:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) for key in ("source", "metric", "quality")
        ):
            raise ValueError("invalid evidence")
        if item["quality"] not in ("COMPLETE", "MISSING", "ERROR"):
            raise ValueError("invalid evidence quality")
        value = item.get("value")
        if (
            not isinstance(value, (str, int, float, type(None)))
            or isinstance(value, bool)
            or isinstance(value, float)
            and not isfinite(value)
        ):
            raise ValueError("invalid evidence value")
        clean_evidence.append(
            {
                key: (
                    _optional_string(item.get(key))
                    if key in ("unit", "period_start", "period_end")
                    else item.get(key)
                )
                for key in (
                    "source",
                    "metric",
                    "value",
                    "unit",
                    "quality",
                    "period_start",
                    "period_end",
                )
            }
        )
    for key in ("currency", "period", "baseline", "optimized", "potential_savings", "confidence"):
        if not isinstance(savings.get(key), str):
            raise ValueError("invalid savings field")
    clean_savings = {
        key: savings[key]
        for key in (
            "currency",
            "period",
            "baseline",
            "optimized",
            "potential_savings",
            "confidence",
        )
    }
    clean_savings["formula"] = savings.get("formula", "UNKNOWN")
    if not isinstance(clean_savings["formula"], str):
        raise ValueError("invalid savings formula")
    for key in ("assumptions", "excluded_costs", "data_sources"):
        clean_savings[key] = _strings(savings.get(key))
    return {
        "finding_id": raw["finding_id"],
        "policy_id": raw["policy_id"],
        "status": raw["status"],
        "resource": {"type": resource["type"], "ref": resource["ref"]},
        "evidence": clean_evidence,
        "risk": {
            "level": risk["level"],
            "reasons": _strings(risk.get("reasons")),
            "unknown_factors": _strings(risk.get("unknown_factors")),
        },
        "savings": clean_savings,
        "explanation": raw["explanation"],
    }


def read_report(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid report JSON") from error
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("schema_version"), str)
        or raw["schema_version"] not in SUPPORTED_VERSIONS
    ):
        raise ValueError("unsupported report schema")
    if raw.get("data_kind") not in ("AWS", "DEMO"):
        raise ValueError("invalid report kind")
    if not isinstance(raw.get("scanned_at"), str) or raw.get("status") not in (
        "COMPLETE",
        "PARTIAL",
        "FAILED",
    ):
        raise ValueError("invalid report status or time")
    scope = raw.get("scope")
    findings = raw.get("findings")
    issues = raw.get("collection_issues")
    if (
        not isinstance(scope, dict)
        or not isinstance(findings, list)
        or not isinstance(issues, list)
    ):
        raise ValueError("invalid report structure")
    clean_findings = [_finding(item) for item in findings]
    ids = [item["finding_id"] for item in clean_findings]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate finding ID")
    clean_issues = []
    for issue in issues:
        if (
            not isinstance(issue, dict)
            or not all(
                isinstance(issue.get(key), str) for key in ("scope", "operation", "category")
            )
            or not isinstance(issue.get("retryable"), bool)
        ):
            raise ValueError("invalid collection issue")
        clean_issues.append(
            {
                key: _optional_string(issue.get(key)) if key == "resource_ref" else issue.get(key)
                for key in ("scope", "operation", "category", "retryable", "resource_ref")
            }
        )
    clean: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "data_kind": raw["data_kind"],
        "scanned_at": raw["scanned_at"],
        "status": raw["status"],
        "scope": {key: _strings(scope.get(key)) for key in ("requested", "completed", "failed")},
        "findings": sorted(clean_findings, key=lambda item: item["finding_id"]),
        "collection_issues": clean_issues,
    }
    if raw["data_kind"] == "DEMO":
        clean["notice"] = "DEMO DATA"
    else:
        clean["account_ref"] = "REDACTED" if raw.get("account_ref") == "REDACTED" else "UNKNOWN"
        if raw.get("analysis_status") not in ("COMPLETE", "PARTIAL", "NOT_EVALUATED"):
            raise ValueError("invalid analysis status")
        clean["analysis_status"] = raw["analysis_status"]
        resources = raw.get("resources")
        if not isinstance(resources, list):
            raise ValueError("invalid resource list")
        clean_resources = []
        for item in resources:
            if not isinstance(item, dict) or not all(
                isinstance(item.get(key), str) for key in ("resource_id", "type", "region", "state")
            ):
                raise ValueError("invalid report resource")
            metrics = item.get("metrics")
            if not isinstance(metrics, dict) or metrics.get("status") not in (
                "COMPLETE",
                "MISSING",
                "ERROR",
                "NOT_REQUESTED",
            ):
                raise ValueError("invalid report metrics")
            average = metrics.get("cpu_average")
            samples = metrics.get("cpu_samples")
            if (
                average is not None
                and (isinstance(average, bool) or not isinstance(average, (int, float)))
            ) or (isinstance(samples, bool) or not isinstance(samples, int) or samples < 0):
                raise ValueError("invalid report metric values")
            if isinstance(average, float) and not isfinite(average):
                raise ValueError("invalid report metric values")
            clean_resources.append(
                {
                    key: _optional_string(item.get(key)) if key == "observed_at" else item.get(key)
                    for key in ("resource_id", "type", "region", "state", "observed_at")
                }
                | {
                    "metrics": {
                        key: (
                            _optional_string(metrics.get(key))
                            if key in ("period_start", "period_end")
                            else metrics.get(key)
                        )
                        for key in (
                            "cpu_average",
                            "cpu_samples",
                            "status",
                            "period_start",
                            "period_end",
                        )
                    }
                }
            )
        clean["resources"] = clean_resources
    return clean
