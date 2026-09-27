"""Wraps any agent to deterministically break "stuck" decision loops.

A loop is declared when the wrapped agent has picked the *same* action for
N consecutive steps while the (coarse) game state also stayed the same --
i.e. the action is not changing anything (e.g. repeatedly choosing
"buscar_vida" while stuck against a wall). ``N`` is ``max_repeat`` by
default, but can be tightened per action via ``action_max_repeat`` --
round 1 found Julia-1 defaults to "esperar" far more than the rule
baseline when nothing is visible, so round 2 watches it with a shorter
leash. When a loop is declared, the guard deterministically overrides the
action using a fixed priority list, so the outcome never depends on
randomness.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, Optional, Sequence, Tuple

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.state import GameState

# Fixed, deterministic order used to pick an alternative when stuck.
_OVERRIDE_PRIORITY: Tuple[Action, ...] = (
    Action.EXPLORE,
    Action.WAIT,
    Action.SEEK_AMMO,
    Action.SEEK_HEALTH,
    Action.FLEE,
    Action.ATTACK,
)


class AntiLoopGuard(DecisionAgent):
    def __init__(
        self,
        agent: DecisionAgent,
        max_repeat: int = 5,
        action_max_repeat: Optional[Dict[Action, int]] = None,
    ) -> None:
        self.agent = agent
        self.max_repeat = max_repeat
        self.action_max_repeat = dict(action_max_repeat or {})
        self.name = f"{agent.name}+antiloop_guard"
        history_capacity = max([max_repeat, *self.action_max_repeat.values()])
        self._history: Deque[Tuple[tuple, Action]] = deque(maxlen=history_capacity)

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        decision = self.agent.decide(state, available_actions)
        signature = state.coarse_signature()
        self._history.append((signature, decision.action))

        if self._is_stuck(decision.action):
            alternative = self._pick_alternative(decision.action, available_actions)
            if alternative != decision.action:
                overridden_from = decision.action
                decision = Decision(
                    action=alternative,
                    confidence=decision.confidence,
                    source=f"{decision.source}+antiloop",
                    model_confidence=decision.model_confidence,
                    probabilities=decision.probabilities,
                    latency_ms=decision.latency_ms,
                    fallback_used=decision.fallback_used,
                    antiloop_override=True,
                    overridden_from=overridden_from,
                    offered_actions=decision.offered_actions,
                    error=decision.error,
                )
                # The override itself becomes the newest history entry, so a
                # forced change of action resets the "stuck" streak instead
                # of being immediately re-detected as stuck next step.
                self._history[-1] = (signature, decision.action)

        return decision

    def _limit_for(self, action: Action) -> int:
        return self.action_max_repeat.get(action, self.max_repeat)

    def _is_stuck(self, action: Action) -> bool:
        limit = self._limit_for(action)
        if len(self._history) < limit:
            return False
        window = list(self._history)[-limit:]
        signatures = {sig for sig, _ in window}
        actions = {act for _, act in window}
        return len(signatures) == 1 and len(actions) == 1

    @staticmethod
    def _pick_alternative(current: Action, available_actions: Sequence[Action]) -> Action:
        for candidate in _OVERRIDE_PRIORITY:
            if candidate != current and candidate in available_actions:
                return candidate
        return current

    def reset(self) -> None:
        self._history.clear()
        self.agent.reset()
