"""Deterministic, rule-based baseline agent.

No model, no randomness: the same state always yields the same action. This
agent is also reused as the fallback strategy when Julia-1's confidence is
below threshold.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.state import GameState


class RuleBasedAgent(DecisionAgent):
    name = "rules"

    def __init__(
        self,
        low_health_threshold: float = 35.0,
        comfortable_ammo_threshold: int = 10,
        max_health: float = 100.0,
    ) -> None:
        self.low_health_threshold = low_health_threshold
        self.comfortable_ammo_threshold = comfortable_ammo_threshold
        self.max_health = max_health

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        action = self._choose(state, available_actions)
        return Decision(action=action, confidence=1.0, source=self.name)

    def _choose(self, s: GameState, available_actions: Sequence[Action]) -> Action:
        low_health = s.health <= self.low_health_threshold
        out_of_ammo = s.ammo <= 0
        enemy_near = s.enemies_visible > 0

        candidates: List[Action] = []
        if low_health and enemy_near and out_of_ammo:
            candidates.append(Action.FLEE)
        if low_health and s.medkit_visible:
            candidates.append(Action.SEEK_HEALTH)
        if out_of_ammo and s.ammo_visible:
            candidates.append(Action.SEEK_AMMO)
        if out_of_ammo and enemy_near:
            candidates.append(Action.FLEE)
        if enemy_near and not out_of_ammo:
            candidates.append(Action.ATTACK)
        if low_health and not enemy_near:
            candidates.append(Action.EXPLORE)
        if s.ammo <= self.comfortable_ammo_threshold and s.ammo_visible:
            candidates.append(Action.SEEK_AMMO)
        if s.medkit_visible and s.health < self.max_health:
            candidates.append(Action.SEEK_HEALTH)
        candidates.append(Action.EXPLORE)
        candidates.append(Action.WAIT)

        chosen = self._first_available(candidates, available_actions)
        if chosen is not None:
            return chosen
        return available_actions[0]

    @staticmethod
    def _first_available(
        candidates: Sequence[Action], available_actions: Sequence[Action]
    ) -> Optional[Action]:
        for action in candidates:
            if action in available_actions:
                return action
        return None
