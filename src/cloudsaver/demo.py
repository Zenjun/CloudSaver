"""Offline fixture using the same opportunity rules as the AWS scan."""

import json
from dataclasses import replace
from importlib.resources import files
from typing import Any

from cloudsaver.domain import Finding, ResourceSnapshot
from cloudsaver.policies import evaluate_all


def scan() -> tuple[str, list[Finding]]:
    """Load bundled fictional data; this function has no AWS or network path."""
    raw: Any = json.loads(files("cloudsaver").joinpath("data/demo.json").read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid demo fixture")
    observed_at = raw.get("observed_at")
    resources = raw.get("resources")
    if not isinstance(observed_at, str) or not isinstance(resources, list):
        raise ValueError("invalid demo fixture")
    snapshots = []
    for item in resources:
        if not isinstance(item, dict):
            raise ValueError("invalid demo resource")
        snapshots.append(replace(ResourceSnapshot.from_mapping(item), observed_at=observed_at))
    return observed_at, evaluate_all(snapshots, provider="demo")
