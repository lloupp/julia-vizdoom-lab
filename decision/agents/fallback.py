"""Julia-1 gated by a confidence threshold, falling back to deterministic rules."""

from __future__ import annotations

from typing import Sequence

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.agents.julia import JuliaAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.state import GameState


class JuliaWithFallbackAgent(DecisionAgent):
    name = "julia+fallback"

    def __init__(
        self,
        julia_agent: JuliaAgent,
        fallback_agent: RuleBasedAgent,
        confidence_threshold: float = 0.6,
    ) -> None:
        self.julia_agent = julia_agent
        self.fallback_agent = fallback_agent
        self.confidence_threshold = confidence_threshold

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        julia_decision = self.julia_agent.decide(state, available_actions)

        use_fallback = (
            julia_decision.error is not None
            or julia_decision.confidence < self.confidence_threshold
        )
        if not use_fallback:
            return Decision(
                action=julia_decision.action,
                confidence=julia_decision.confidence,
                source=self.name,
                model_confidence=julia_decision.model_confidence,
                probabilities=julia_decision.probabilities,
                latency_ms=julia_decision.latency_ms,
                fallback_used=False,
                offered_actions=julia_decision.offered_actions,
                error=None,
            )

        rule_decision = self.fallback_agent.decide(state, available_actions)
        return Decision(
            action=rule_decision.action,
            confidence=rule_decision.confidence,
            source=self.name,
            model_confidence=julia_decision.model_confidence,
            probabilities=julia_decision.probabilities,
            latency_ms=julia_decision.latency_ms,
            fallback_used=True,
            offered_actions=julia_decision.offered_actions,
            error=julia_decision.error,
        )

    def reset(self) -> None:
        self.julia_agent.reset()
        self.fallback_agent.reset()
