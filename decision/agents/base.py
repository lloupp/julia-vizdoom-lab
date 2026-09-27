"""Common interface every decision agent implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from decision.actions import Action
from decision.state import GameState


@dataclass(frozen=True)
class Decision:
    """Result of one decision step, always produced regardless of agent type.

    ``confidence`` is the confidence of the action that was actually
    executed (1.0 for rule-based decisions, since rules are certain by
    construction). ``model_confidence`` is Julia-1's raw top-choice softmax
    probability (``max_probability``), kept even when a fallback overrides
    that choice, so reporting can tell "how sure was the model" apart from
    "how sure was the system in what it did". This is NOT a calibrated
    confidence -- it is not validated to track actual correctness rates, so
    treat it as a raw model score, not a probability of being right.
    """

    action: Action
    confidence: float
    source: str
    model_confidence: Optional[float] = None
    probabilities: Dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    fallback_used: bool = False
    antiloop_override: bool = False
    overridden_from: Optional[Action] = None
    offered_actions: Optional[Sequence[Action]] = None
    error: Optional[str] = None


class DecisionAgent(ABC):
    """Interface: state -> action + confidence.

    Implementations must be deterministic given the same inputs and internal
    history, except for the model-backed agent whose *confidence* naturally
    varies with inference but whose action selection given fixed
    probabilities is still deterministic (argmax).
    """

    name: str = "agent"

    @abstractmethod
    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        """Choose one of ``available_actions`` for the given ``state``."""

    def reset(self) -> None:
        """Clear any per-episode internal state. No-op by default."""
        return None
