"""Action vocabulary shared by every agent."""

from __future__ import annotations

from enum import Enum
from typing import Tuple


class Action(str, Enum):
    ATTACK = "atacar"
    FLEE = "fugir"
    SEEK_HEALTH = "buscar_vida"
    SEEK_AMMO = "buscar_municao"
    EXPLORE = "explorar"
    WAIT = "esperar"


# Human-readable descriptions used as decision criteria for Julia-1 and as
# documentation for the rule-based agent. Keep these short and factual: they
# are read by the model, not by a human end user.
ACTION_DESCRIPTIONS = {
    Action.ATTACK: "Attack the visible enemy. Requires ammo and an enemy in sight.",
    Action.FLEE: "Retreat from danger, away from visible enemies.",
    Action.SEEK_HEALTH: "Move toward a visible medkit to recover health.",
    Action.SEEK_AMMO: "Move toward visible ammo to restock.",
    Action.EXPLORE: "Move to a new area looking for items or enemies.",
    Action.WAIT: "Stay in place and do nothing this step.",
}

ALL_ACTIONS: Tuple[Action, ...] = tuple(Action)
