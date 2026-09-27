"""The 4 decision modes under comparison.

Mode 3 (parallel) needs each model's historical per-category accuracy to
break non-sensitive disagreements -- that comes from modes 1 and 2's own
results, so the harness must run modes 1 and 2 before instantiating mode 3
(see run_eval.py). Both models are deterministic encoders (no sampling), so
repeating the same task multiple times yields identical output every time;
the "historical accuracy" used here is exactly what a single pass over the
task set already tells us.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from agent_decision_eval.actions import Action, SENSITIVE_ACTIONS
from agent_decision_eval.models.base import DecisionModel, ModelDecision
from agent_decision_eval.tasks import Task

# When a parallel-mode disagreement touches a sensitive action, the system
# must not auto-execute either proposal. ANSWER is the safe fallback: it
# surfaces the disagreement/uncertainty to the user instead of acting, and
# unlike STOP it doesn't abandon the turn outright.
SAFE_FALLBACK_ACTION = Action.ANSWER


@dataclass(frozen=True)
class ModeDecision:
    final_action: Action
    source: str
    laya: Optional[ModelDecision] = None
    julia: Optional[ModelDecision] = None
    used_fallback: bool = False
    divergence: bool = False
    blocked_sensitive: bool = False
    total_latency_ms: float = 0.0
    error: Optional[str] = None


class LayaOnlyMode:
    name = "laya_only"

    def __init__(self, laya: DecisionModel) -> None:
        self.laya = laya

    def decide(self, task: Task, options: Sequence[Action]) -> ModeDecision:
        start = time.perf_counter()
        d = self.laya.predict(task, options)
        total = (time.perf_counter() - start) * 1000
        return ModeDecision(final_action=d.choice, source="laya", laya=d, total_latency_ms=total, error=d.error)


class JuliaOnlyMode:
    name = "julia_only"

    def __init__(self, julia: DecisionModel) -> None:
        self.julia = julia

    def decide(self, task: Task, options: Sequence[Action]) -> ModeDecision:
        start = time.perf_counter()
        d = self.julia.predict(task, options)
        total = (time.perf_counter() - start) * 1000
        return ModeDecision(final_action=d.choice, source="julia", julia=d, total_latency_ms=total, error=d.error)


@dataclass
class CategoryAccuracy:
    """Historical accuracy stats mode 3 uses to break non-sensitive ties."""

    read_only_accuracy: Dict[str, float] = field(default_factory=dict)  # {"laya": 0.9, "julia": 0.8}
    overall_accuracy: Dict[str, float] = field(default_factory=dict)


class ParallelMode:
    name = "parallel"

    def __init__(self, laya: DecisionModel, julia: DecisionModel, history: CategoryAccuracy) -> None:
        self.laya = laya
        self.julia = julia
        self.history = history

    def _preferred_model_for_read_only(self) -> str:
        laya_acc = self.history.read_only_accuracy.get("laya")
        julia_acc = self.history.read_only_accuracy.get("julia")
        if laya_acc is not None and julia_acc is not None and laya_acc != julia_acc:
            return "laya" if laya_acc > julia_acc else "julia"
        # Tied (or missing) read-only history: fall back to overall accuracy,
        # then to a fixed, documented default so the rule is always
        # deterministic.
        laya_overall = self.history.overall_accuracy.get("laya")
        julia_overall = self.history.overall_accuracy.get("julia")
        if laya_overall is not None and julia_overall is not None and laya_overall != julia_overall:
            return "laya" if laya_overall > julia_overall else "julia"
        return "laya"

    def decide(self, task: Task, options: Sequence[Action]) -> ModeDecision:
        start = time.perf_counter()
        laya_d = self.laya.predict(task, options)
        julia_d = self.julia.predict(task, options)
        total = (time.perf_counter() - start) * 1000
        error = laya_d.error or julia_d.error

        if laya_d.choice == julia_d.choice:
            return ModeDecision(
                final_action=laya_d.choice,
                source="agreement",
                laya=laya_d,
                julia=julia_d,
                divergence=False,
                total_latency_ms=total,
                error=error,
            )

        # Disagreement: never combine confidences arithmetically. If either
        # side proposes a sensitive action, do not auto-execute anything --
        # a wrong "write"/"edit"/"bash" is categorically worse than a wrong
        # read-only pick.
        sensitive_involved = laya_d.choice in SENSITIVE_ACTIONS or julia_d.choice in SENSITIVE_ACTIONS
        if sensitive_involved:
            return ModeDecision(
                final_action=SAFE_FALLBACK_ACTION,
                source="divergence:sensitive_blocked",
                laya=laya_d,
                julia=julia_d,
                divergence=True,
                blocked_sensitive=True,
                total_latency_ms=total,
                error=error,
            )

        preferred = self._preferred_model_for_read_only()
        chosen = laya_d if preferred == "laya" else julia_d
        return ModeDecision(
            final_action=chosen.choice,
            source=f"divergence:prefer_{preferred}",
            laya=laya_d,
            julia=julia_d,
            divergence=True,
            total_latency_ms=total,
            error=error,
        )


class PrimaryFallbackMode:
    """Laya is primary; Julia is consulted only below a confidence threshold."""

    name = "primary_fallback"

    def __init__(self, laya: DecisionModel, julia: DecisionModel, confidence_threshold: float = 0.7) -> None:
        self.laya = laya
        self.julia = julia
        self.confidence_threshold = confidence_threshold

    def decide(self, task: Task, options: Sequence[Action]) -> ModeDecision:
        start = time.perf_counter()
        laya_d = self.laya.predict(task, options)

        gate_value = laya_d.model_confidence if laya_d.model_confidence is not None else laya_d.max_probability
        use_fallback = laya_d.error is not None or gate_value < self.confidence_threshold

        if not use_fallback:
            total = (time.perf_counter() - start) * 1000
            return ModeDecision(
                final_action=laya_d.choice,
                source="primary",
                laya=laya_d,
                used_fallback=False,
                total_latency_ms=total,
                error=laya_d.error,
            )

        julia_d = self.julia.predict(task, options)
        total = (time.perf_counter() - start) * 1000
        return ModeDecision(
            final_action=julia_d.choice,
            source="fallback",
            laya=laya_d,
            julia=julia_d,
            used_fallback=True,
            total_latency_ms=total,
            error=laya_d.error or julia_d.error,
        )
