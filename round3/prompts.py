"""Canonical state and question schema for round 3.

The schema follows the model cards: explicit state, typed questions, clear
criteria, fixed option order, and descriptive false/true criteria for noul.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from decision.actions import ALL_ACTIONS, Action
from decision.state import GameState

FIXED_ACTION_ORDER = tuple(ALL_ACTIONS)

ACTION_CRITERIA: Dict[Action, str] = {
    Action.ATTACK: (
        "Engage a currently visible enemy with the equipped weapon. "
        "Only valid when an enemy is visible and ammunition is available."
    ),
    Action.FLEE: (
        "Create distance from a currently visible enemy when immediate survival "
        "is more important than dealing damage."
    ),
    Action.SEEK_HEALTH: (
        "Move toward a currently visible health pickup to recover health."
    ),
    Action.SEEK_AMMO: (
        "Move toward currently visible ammunition to restore combat capability."
    ),
    Action.EXPLORE: (
        "Move through the map to find enemies or useful resources when no more "
        "urgent action is preferable."
    ),
    Action.WAIT: (
        "Deliberately pause for one decision interval only when acting now is "
        "worse than pausing. Do not use this as a generic default."
    ),
}

BOOLEAN_QUESTIONS = {
    "survival_priority": {
        "type": "noul",
        "instructions": (
            "Given the current state and objective, should immediate survival "
            "take priority over combat, resource collection, and exploration?"
        ),
        "criteria": {
            "false": "No. Immediate survival does not need to override the other objectives.",
            "true": "Yes. Avoiding imminent death should take priority right now.",
        },
    },
    "engage_enemy": {
        "type": "noul",
        "instructions": (
            "Given the current state and objective, should the agent engage a "
            "currently visible enemy now?"
        ),
        "criteria": {
            "false": "No. Do not initiate or continue an attack right now.",
            "true": "Yes. Attacking a visible enemy is appropriate right now.",
        },
    },
    "seek_health": {
        "type": "noul",
        "instructions": (
            "Given the current state and objective, should the agent actively "
            "move toward a currently visible health pickup now?"
        ),
        "criteria": {
            "false": "No. Seeking health is not the preferred objective right now.",
            "true": "Yes. Recovering health should be pursued right now.",
        },
    },
    "seek_ammo": {
        "type": "noul",
        "instructions": (
            "Given the current state and objective, should the agent actively "
            "move toward currently visible ammunition now?"
        ),
        "criteria": {
            "false": "No. Seeking ammunition is not the preferred objective right now.",
            "true": "Yes. Restocking ammunition should be pursued right now.",
        },
    },
}


def health_band(value: float) -> str:
    if value <= 25:
        return "critical"
    if value <= 50:
        return "low"
    if value <= 75:
        return "medium"
    return "high"


def ammo_band(value: int) -> str:
    if value <= 0:
        return "empty"
    if value <= 5:
        return "low"
    if value <= 20:
        return "medium"
    return "enough"


def distance_band(distance: float | None) -> str:
    if distance is None:
        return "none_or_unknown"
    if distance <= 300:
        return "close"
    if distance <= 700:
        return "medium"
    return "far"


def ordered_actions(available_actions: Sequence[Action]) -> List[Action]:
    available = set(available_actions)
    return [action for action in FIXED_ACTION_ORDER if action in available]


def choice_criteria(actions: Sequence[Action]) -> Dict[str, str]:
    return {action.value: ACTION_CRITERIA[action] for action in ordered_actions(actions)}


def build_model_state(state: GameState, available_actions: Sequence[Action]) -> dict:
    actions = ordered_actions(available_actions)
    return {
        "objective": (
            "Survive as long as possible while eliminating enemies when doing "
            "so is reasonable, and maintain enough health and ammunition to continue."
        ),
        "health": {"value": round(float(state.health), 2), "band": health_band(state.health)},
        "ammo": {"value": int(state.ammo), "band": ammo_band(state.ammo)},
        "enemy": {
            "visible_count": int(state.enemies_visible),
            "nearest_distance": (
                None if state.enemy_distance is None else round(float(state.enemy_distance), 1)
            ),
            "distance_band": distance_band(state.enemy_distance),
        },
        "visible_pickups": {
            "health": bool(state.medkit_visible),
            "ammo": bool(state.ammo_visible),
        },
        "available_actions": [
            {"id": action.value, "meaning": ACTION_CRITERIA[action]} for action in actions
        ],
    }
