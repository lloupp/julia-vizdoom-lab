"""Pure functions that turn raw JSONL logs into episode/variant metrics.

Kept dependency-free (no numpy/pandas) on purpose: this is meant to be easy
to read line by line and to reuse in decision-layer-only projects.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional


def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def percentile(values: List[float], p: float) -> Optional[float]:
    """Linear-interpolation percentile, p in [0, 100]. None if values is empty."""
    if not values:
        return None
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    rank = (p / 100.0) * (len(data) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return data[low]
    frac = rank - low
    return data[low] + (data[high] - data[low]) * frac


def mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def compute_episode_metrics(decisions: List[dict], episode_summary: dict) -> dict:
    """Merge per-decision stats with the env-derived episode summary row."""
    confidences = [d["confidence"] for d in decisions]
    model_confidences = [d["model_confidence"] for d in decisions if d["model_confidence"] is not None]
    latencies = [d["latency_ms"] for d in decisions]
    fallback_count = sum(1 for d in decisions if d["fallback_used"])
    antiloop_count = sum(1 for d in decisions if d["antiloop_override"])
    error_count = sum(1 for d in decisions if d["error"])
    invalid_count = sum(
        1 for d in decisions if d["action"] not in d["available_actions"]
    )

    return {
        **episode_summary,
        "decisions": len(decisions),
        "avg_confidence": mean(confidences),
        "avg_model_confidence": mean(model_confidences),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_count / len(decisions) if decisions else None,
        "antiloop_override_count": antiloop_count,
        "avg_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "error_count": error_count,
        "invalid_action_count": invalid_count,
    }


def aggregate_variant(episode_metrics: List[dict]) -> dict:
    """Mean across episodes for every numeric field, plus episode count."""
    if not episode_metrics:
        return {}

    numeric_fields = [
        "survival_tics",
        "survival_seconds",
        "kills",
        "damage_taken",
        "ammo_consumed",
        "decisions",
        "avg_confidence",
        "avg_model_confidence",
        "fallback_count",
        "fallback_rate",
        "antiloop_override_count",
        "avg_latency_ms",
        "p95_latency_ms",
        "error_count",
        "invalid_action_count",
    ]
    out: Dict[str, Optional[float]] = {"episodes": len(episode_metrics)}
    for field in numeric_fields:
        values = [e[field] for e in episode_metrics if e.get(field) is not None]
        out[field] = mean(values)
    out["death_rate"] = mean([1.0 if e["died"] else 0.0 for e in episode_metrics])
    return out
