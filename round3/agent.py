"""Event-driven round-3 agent shared by both model backends."""

from __future__ import annotations

from typing import Optional, Sequence

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.state import GameState
from round3.backends import DecisionBackend
from round3.hierarchy import decide_hierarchically
from round3.prompts import ammo_band, distance_band, health_band, ordered_actions


def event_signature(state: GameState, available_actions: Sequence[Action]) -> tuple:
    enemies_band = 0 if state.enemies_visible <= 0 else (1 if state.enemies_visible == 1 else 2)
    return (
        health_band(state.health),
        ammo_band(state.ammo),
        enemies_band,
        distance_band(state.enemy_distance),
        bool(state.medkit_visible),
        bool(state.ammo_visible),
        tuple(action.value for action in ordered_actions(available_actions)),
    )


class Round3ModelAgent(DecisionAgent):
    """Hierarchical typed decisions, refreshed on events instead of every loop."""

    def __init__(
        self,
        backend: DecisionBackend,
        max_hold_steps: int = 4,
        fallback_agent: Optional[RuleBasedAgent] = None,
    ) -> None:
        if max_hold_steps < 1:
            raise ValueError("max_hold_steps must be >= 1")
        self.backend = backend
        self.max_hold_steps = max_hold_steps
        self.fallback_agent = fallback_agent or RuleBasedAgent()
        self.name = f"{backend.name}_recommended"
        self._cached_signature: Optional[tuple] = None
        self._cached_decision: Optional[Decision] = None
        self._hold_steps = 0
        self.last_trace: dict = {}

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        available = ordered_actions(available_actions)
        signature = event_signature(state, available)

        if (
            self._cached_signature == signature
            and self._cached_decision is not None
            and self._cached_decision.action in available
            and self._hold_steps < self.max_hold_steps
        ):
            self._hold_steps += 1
            cached = Decision(
                action=self._cached_decision.action,
                confidence=self._cached_decision.confidence,
                source=f"{self.name}:event_cache",
                model_confidence=None,
                probabilities={},
                latency_ms=0.0,
                offered_actions=available,
            )
            self.last_trace = {
                "backend": self.backend.name,
                "cache_hit": True,
                "model_calls": 0,
                "stage": "event_cache",
                "score_kind": "cached",
                "score_is_calibrated": False,
                "boolean_probabilities": {},
                "backend_metadata": [],
            }
            return cached

        try:
            result = decide_hierarchically(self.backend, state, available)
            model_confidence = result.score if result.score_is_calibrated else None
            decision = Decision(
                action=result.action,
                confidence=result.score,
                source=self.name,
                model_confidence=model_confidence,
                probabilities=result.probabilities,
                latency_ms=result.latency_ms,
                offered_actions=available,
            )
            self.last_trace = {
                "backend": self.backend.name,
                "cache_hit": False,
                "model_calls": result.model_calls,
                "stage": result.stage,
                "score_kind": result.score_kind,
                "score_is_calibrated": result.score_is_calibrated,
                "boolean_probabilities": result.boolean_probabilities,
                "backend_metadata": result.backend_metadata,
            }
        except Exception as exc:
            fallback = self.fallback_agent.decide(state, available)
            decision = Decision(
                action=fallback.action,
                confidence=fallback.confidence,
                source=f"{self.name}:error_fallback",
                model_confidence=None,
                probabilities={},
                latency_ms=0.0,
                fallback_used=True,
                offered_actions=available,
                error=f"{type(exc).__name__}: {exc}",
            )
            self.last_trace = {
                "backend": self.backend.name,
                "cache_hit": False,
                "model_calls": 0,
                "stage": "error_fallback",
                "score_kind": "rule_fallback",
                "score_is_calibrated": True,
                "boolean_probabilities": {},
                "backend_metadata": [],
                "error": decision.error,
            }

        self._cached_signature = signature
        self._cached_decision = decision
        self._hold_steps = 0
        return decision

    def reset(self) -> None:
        self._cached_signature = None
        self._cached_decision = None
        self._hold_steps = 0
        self.last_trace = {}
        self.fallback_agent.reset()
