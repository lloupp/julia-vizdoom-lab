"""Deterministic pre-filter: narrows available actions before a model decides.

This never picks the final action. It only removes options that are unsafe
or pointless given the current state; whichever agent it wraps (Julia-1 or
anything else) still does the choosing among what survives the filter.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, List, Sequence

from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.state import GameState

# Health at or below this is "critical": survival options take priority over
# everything else (attacking, exploring, waiting).
CRITICAL_HEALTH = 25.0

FilterFn = Callable[[GameState, Sequence[Action]], List[Action]]


def filter_actions(state: GameState, available: Sequence[Action]) -> List[Action]:
    """Narrow ``available`` deterministically. Never introduces an action
    that wasn't already in ``available``; order is preserved.

    Rules (independent, applied in order):
    1. No ammo -> never offer ATTACK (belt-and-suspenders: the environment
       should already exclude it, but the decision layer must not depend on
       that holding for every possible game backend).
    2. Critical health -> if SEEK_HEALTH or FLEE is available, offer only
       survival options.
    3. No danger and no objective visible (no enemy, no medkit, no ammo) ->
       do not allow indefinite WAIT; drop it so at least EXPLORE remains.

    This can narrow down to a single action (e.g. just EXPLORE, when nothing
    is visible and WAIT gets dropped) -- callers that need >=2 candidates for
    a model call (Julia-1 requires 2-20) must handle that themselves; see
    ``ActionFilterGuard``.
    """
    actions = list(available)
    kept = set(actions)

    if state.ammo <= 0:
        kept.discard(Action.ATTACK)

    if state.health <= CRITICAL_HEALTH:
        survival = {a for a in (Action.SEEK_HEALTH, Action.FLEE) if a in kept}
        if survival:
            kept = survival

    no_danger_or_goal = (
        state.enemies_visible == 0 and not state.medkit_visible and not state.ammo_visible
    )
    if no_danger_or_goal and Action.WAIT in kept and len(kept) > 1:
        kept = kept - {Action.WAIT}

    return [a for a in actions if a in kept]


class ActionFilterGuard(DecisionAgent):
    """Applies ``filter_fn`` before delegating to the wrapped agent.

    If filtering leaves only one action, there is nothing left to actually
    choose between: rather than force a fake multi-option call onto a model
    that requires 2-20 candidates, that single action is taken directly
    (source suffixed ``:forced``), still without ever inventing an action
    that filtering didn't already leave on the table.
    """

    def __init__(self, agent: DecisionAgent, filter_fn: FilterFn = filter_actions) -> None:
        self.agent = agent
        self.filter_fn = filter_fn
        self.name = f"{agent.name}+filtered"

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        filtered = self.filter_fn(state, available_actions)
        if len(filtered) < 2:
            only = filtered[0] if filtered else available_actions[0]
            return Decision(
                action=only,
                confidence=1.0,
                source=f"{self.name}:forced",
                offered_actions=list(filtered) or [only],
            )
        decision = self.agent.decide(state, filtered)
        if decision.offered_actions is None:
            decision = replace(decision, offered_actions=list(filtered))
        return decision

    def reset(self) -> None:
        self.agent.reset()
