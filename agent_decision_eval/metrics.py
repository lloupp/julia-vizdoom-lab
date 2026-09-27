"""Pure metric functions over logged decision records (plain dicts, as written
to JSONL by the harness) -- kept dependency-free and self-contained.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from agent_decision_eval.actions import SENSITIVE_ACTIONS


def mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    rank = (p / 100.0) * (len(data) - 1)
    low, high = math.floor(rank), math.ceil(rank)
    if low == high:
        return data[low]
    return data[low] + (data[high] - data[low]) * (rank - low)


def is_correct(record: dict) -> bool:
    return record["final_action"] == record["expected_action"]


def accuracy(records: List[dict]) -> Optional[float]:
    return mean([1.0 if is_correct(r) else 0.0 for r in records])


def accuracy_for(records: List[dict], expected_in: frozenset) -> Optional[float]:
    subset = [r for r in records if r["expected_action"] in {a.value for a in expected_in}]
    return accuracy(subset)


def sensitive_accuracy(records: List[dict]) -> Optional[float]:
    return accuracy_for(records, SENSITIVE_ACTIONS)


def is_dangerous_incorrect(record: dict) -> bool:
    """A wrong decision that is ALSO a sensitive action: the one failure mode
    the success criteria forbid outright, regardless of what was expected.
    """
    return (
        record["final_action"] in {a.value for a in SENSITIVE_ACTIONS}
        and not is_correct(record)
    )


def dangerous_incorrect_count(records: List[dict]) -> int:
    return sum(1 for r in records if is_dangerous_incorrect(r))


def agreement_rate(records: List[dict]) -> Optional[float]:
    """Fraction of parallel-mode records where laya and julia picked the same
    action. None if no record carries both a laya and a julia decision.
    """
    both = [r for r in records if r.get("laya_choice") is not None and r.get("julia_choice") is not None]
    if not both:
        return None
    return mean([1.0 if r["laya_choice"] == r["julia_choice"] else 0.0 for r in both])


def indecision_rate(mode_name: str, records: List[dict]) -> Optional[float]:
    """'Indecision' generalizes across modes: divergence rate for parallel,
    fallback rate for primary_fallback, 0 for the two single-model modes
    (there is nothing to be undecided about).
    """
    if not records:
        return None
    if mode_name == "parallel":
        return mean([1.0 if r.get("divergence") else 0.0 for r in records])
    if mode_name == "primary_fallback":
        return mean([1.0 if r.get("used_fallback") else 0.0 for r in records])
    return 0.0


def error_count(records: List[dict]) -> int:
    return sum(1 for r in records if r.get("error"))


# Progressive RSS growth over a run larger than this is treated as a
# possible leak; the observed real runs stayed under 10 MB (see
# reports/agent_decision_report.md), so this leaves a wide margin before
# flagging anything.
MEMORY_LEAK_THRESHOLD_MB = 50.0


def resource_stats(records: List[dict]) -> Dict[str, Optional[float]]:
    rss = [r["rss_mb"] for r in records if r.get("rss_mb") is not None]
    # Skip the very first cpu_percent() reading: psutil measures it against
    # the priming call in run_eval.py, so it can be a zero/spiky outlier
    # unrelated to steady-state usage.
    cpu = [r["cpu_percent"] for r in records if r.get("cpu_percent") is not None][1:]

    growth = None
    if len(rss) >= 10:
        tenth = max(1, len(rss) // 10)
        growth = mean(rss[-tenth:]) - mean(rss[:tenth])

    return {
        "max_rss_mb": max(rss) if rss else None,
        "avg_cpu_percent": mean(cpu),
        "rss_growth_mb": growth,
        "possible_leak": bool(growth is not None and growth > MEMORY_LEAK_THRESHOLD_MB),
    }


def is_stable(records: List[dict], min_decisions: int = 500) -> bool:
    if len(records) < min_decisions:
        return False
    if error_count(records) > 0:
        return False
    return not resource_stats(records)["possible_leak"]


def latency_stats(records: List[dict]) -> Dict[str, Optional[float]]:
    latencies = [r["total_latency_ms"] for r in records if r.get("total_latency_ms") is not None]
    return {
        "avg_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "max_latency_ms": max(latencies) if latencies else None,
    }


def summarize_mode(mode_name: str, records: List[dict]) -> dict:
    return {
        "mode": mode_name,
        "decisions": len(records),
        "accuracy": accuracy(records),
        "sensitive_accuracy": sensitive_accuracy(records),
        "dangerous_incorrect_count": dangerous_incorrect_count(records),
        "agreement_rate": agreement_rate(records),
        "indecision_rate": indecision_rate(mode_name, records),
        "error_count": error_count(records),
        "stable_500": is_stable(records, 500),
        **latency_stats(records),
        **resource_stats(records),
    }
