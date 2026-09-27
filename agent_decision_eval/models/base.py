"""Common interface every decision model wrapper implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from agent_decision_eval.actions import Action
from agent_decision_eval.tasks import Task


@dataclass(frozen=True)
class ModelDecision:
    """One model's raw output for one task, before any mode-level policy.

    ``max_probability`` is the winning option's raw softmax probability --
    NOT a calibrated confidence (both model cards say so explicitly; see
    reports/agent_decision_report.md). ``model_confidence`` is a distinct,
    separately-computed confidence value only some models expose (Laya
    does; Julia-1 doesn't, so it's None there) -- kept apart from
    ``max_probability`` so the two are never conflated.
    """

    choice: Action
    probabilities: Dict[str, float] = field(default_factory=dict)
    max_probability: float = 0.0
    model_confidence: Optional[float] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


class DecisionModel(ABC):
    name: str = "model"

    @abstractmethod
    def predict(self, task: Task, options: Sequence[Action]) -> ModelDecision:
        """Choose one of ``options`` for ``task``."""
