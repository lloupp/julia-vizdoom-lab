"""Direct choice policy for mutually exclusive VizDoom actions.

Action selection is a mutually exclusive decision, so round 3C asks exactly
one typed `choice` question over only the actions that are currently valid.
There is no boolean gate, no learned confidence threshold, and no benchmark-
fitted rule before the choice.

Julia and Laya receive the same structured state, the same fixed candidate
order, and the same semantic action descriptions. The only difference is the
model backend.
"""

from __future__ import annotations

from typing import Optional, Sequence

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.state import GameState
from round3.agent import event_signature
from round3.backends import DecisionBackend
from round3.prompts import build_model_state, choice_criteria, ordered_actions


class DirectChoiceAgent(DecisionAgent):
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
        self.name = f"{backend.name}_direct_choice"
        self._cached_signature: Optional[tuple] = None
        self._cached_decision: Optional[Decision] = None
        self._hold_steps = 0
        self.last_trace: dict = {}

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        available = ordered_actions(available_actions)
        if not available:
            raise ValueError("No available actions")

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
                "candidate_count": len(available),
                "score_kind": "cached",
                "score_is_calibrated": False,
                "backend_metadata": [],
            }
            return cached

        if len(available) == 1:
            decision = Decision(
                action=available[0],
                confidence=1.0,
                source=f"{self.name}:single_valid_action",
                model_confidence=None,
                probabilities={},
                latency_ms=0.0,
                offered_actions=available,
            )
            self.last_trace = {
                "backend": self.backend.name,
                "cache_hit": False,
                "model_calls": 0,
                "stage": "single_valid_action",
                "candidate_count": 1,
                "score_kind": "forced_single_valid_action",
                "score_is_calibrated": False,
                "backend_metadata": [],
            }
            self._cached_signature = signature
            self._cached_decision = decision
            self._hold_steps = 0
            return decision

        try:
            model_state = build_model_state(state, available)
            questions = {
                "action": {
                    "type": "choice",
                    "instructions": (
                        "Choose exactly one action for the agent to execute next. "
                        "The options are mutually exclusive and all listed options "
                        "are currently executable. Use the game state and objective "
                        "to select the best immediate action."
                    ),
                    "criteria": choice_criteria(available),
                }
            }
            batch = self.backend.predict(model_state, questions)
            answer = batch.answers["action"]
            choice_id = str(answer["choice"])
            valid_ids = {action.value for action in available}
            if choice_id not in valid_ids:
                raise ValueError(
                    f"Model returned unavailable action {choice_id!r}; "
                    f"valid={sorted(valid_ids)}"
                )

            score, score_kind, calibrated = self.backend.choice_score(answer)
            probabilities = {
                str(key): float(value)
                for key, value in dict(answer.get("probabilities") or {}).items()
            }
            decision = Decision(
                action=Action(choice_id),
                confidence=score,
                source=self.name,
                model_confidence=score if calibrated else None,
                probabilities=probabilities,
                latency_ms=batch.latency_ms,
                offered_actions=available,
            )
            self.last_trace = {
                "backend": self.backend.name,
                "cache_hit": False,
                "model_calls": 1,
                "stage": "direct_choice",
                "candidate_count": len(available),
                "score_kind": score_kind,
                "score_is_calibrated": calibrated,
                "backend_metadata": [batch.metadata],
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
                "candidate_count": len(available),
                "score_kind": "rule_fallback",
                "score_is_calibrated": True,
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
