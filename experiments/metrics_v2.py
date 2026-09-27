"""Round-2-specific metrics: additive on top of experiments/metrics.py.

Kept separate from ``metrics.py`` (round 1) rather than editing it in place,
because round 1's report must keep computing exactly what it already
computes. Round 2 introduces two wrinkles round 1 didn't have:

1. ``ActionFilterGuard`` can short-circuit to a single forced action without
   ever calling Julia-1 (``model_confidence`` is None on that record). Mixing
   those zero-latency, no-call steps into a "Julia latency" average would
   silently deflate it -- the same class of bug as round 1's ammo-tracking
   mistake, so this time latency and confidence stats explicitly exclude
   forced steps.
2. Every Julia-based decision is logged alongside what the deterministic
   rule agent would have done from the same (state, available_actions), so
   we can measure agreement without it affecting behavior.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from experiments.metrics import mean, percentile


def is_real_model_call(decision: dict) -> bool:
    """True iff Julia-1 was actually invoked for this step.

    False for rule-only decisions (``model_confidence`` is always None
    there) and for ``ActionFilterGuard`` "forced" steps (only one action
    survived filtering, so nothing was actually asked of the model).
    """
    return decision.get("model_confidence") is not None


def is_forced(decision: dict) -> bool:
    """True iff only one action was actually offered for this step.

    This is the exact condition ``ActionFilterGuard`` uses to short-circuit
    Julia-1 (see decision/agents/filter.py), checked structurally via
    ``offered_actions`` rather than inferred from confidence/fallback flags
    -- the environment always offers at least 2 actions (EXPLORE+WAIT at
    minimum), so a length-1 ``offered_actions`` can only come from that
    filter, never from a plain rule-agent or an unfiltered Julia decision.
    """
    return len(decision.get("offered_actions", [])) < 2


def action_distribution(decisions: List[dict]) -> Dict[str, int]:
    return dict(Counter(d["action"] for d in decisions))


def agreement_rate(decisions: List[dict]) -> Optional[float]:
    """Fraction of decisions where the executed action matches the rule
    agent's shadow decision from the very same (state, available_actions).
    None if no decision carries a shadow action (e.g. the "rules" variant,
    which trivially agrees with itself and isn't logged with a shadow).
    """
    matches = [
        d["action"] == d["rule_shadow_action"] for d in decisions if "rule_shadow_action" in d
    ]
    return mean([1.0 if m else 0.0 for m in matches]) if matches else None


def compute_episode_metrics_v2(decisions: List[dict], episode_summary: dict) -> dict:
    """Round-2 episode metrics: everything round 1 tracked, plus the above."""
    confidences = [d["confidence"] for d in decisions]
    real_calls = [d for d in decisions if is_real_model_call(d)]
    model_confidences = [d["model_confidence"] for d in real_calls]
    latencies = [d["latency_ms"] for d in real_calls]

    fallback_count = sum(1 for d in decisions if d["fallback_used"])
    antiloop_count = sum(1 for d in decisions if d["antiloop_override"])
    wait_override_count = sum(
        1 for d in decisions if d["antiloop_override"] and d.get("overridden_from") == "esperar"
    )
    forced_count = sum(1 for d in decisions if is_forced(d))
    error_count = sum(1 for d in decisions if d["error"])
    invalid_count = sum(
        1 for d in decisions if d["action"] not in d.get("offered_actions", d["available_actions"])
    )

    return {
        **episode_summary,
        "decisions": len(decisions),
        "action_distribution": action_distribution(decisions),
        "avg_confidence": mean(confidences),
        "avg_model_confidence": mean(model_confidences),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_count / len(decisions) if decisions else None,
        "antiloop_override_count": antiloop_count,
        "wait_override_count": wait_override_count,
        "forced_count": forced_count,
        "forced_rate": forced_count / len(decisions) if decisions else None,
        "avg_latency_ms": mean(latencies),
        "p95_latency_ms": percentile(latencies, 95),
        "real_model_calls": len(real_calls),
        "error_count": error_count,
        "invalid_action_count": invalid_count,
        "agreement_rate": agreement_rate(decisions),
    }


def aggregate_variant_v2(episode_metrics: List[dict]) -> dict:
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
        "wait_override_count",
        "forced_count",
        "forced_rate",
        "avg_latency_ms",
        "p95_latency_ms",
        "real_model_calls",
        "error_count",
        "invalid_action_count",
        "agreement_rate",
    ]
    out: Dict[str, Optional[float]] = {"episodes": len(episode_metrics)}
    for field in numeric_fields:
        values = [e[field] for e in episode_metrics if e.get(field) is not None]
        out[field] = mean(values)
    out["death_rate"] = mean([1.0 if e["died"] else 0.0 for e in episode_metrics])

    total_distribution: Counter = Counter()
    for e in episode_metrics:
        total_distribution.update(e.get("action_distribution", {}))
    out["action_distribution_total"] = dict(total_distribution)

    return out


def by_seed(episode_metrics: List[dict], field: str) -> Dict[int, float]:
    """Maps seed -> metric value, for paired statistical comparisons."""
    return {
        e["seed"]: e[field]
        for e in episode_metrics
        if e.get(field) is not None and "seed" in e
    }
