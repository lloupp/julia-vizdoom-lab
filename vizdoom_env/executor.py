"""Deterministic mapping from Action to low-level VizDoom buttons.

Every function here is a pure function of its inputs: the same action and
the same (player position, player angle, nearest target) always produce the
exact same button combination. No randomness, no hidden state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from decision.actions import Action

Point = Tuple[float, float]

BUTTON_NAMES = (
    "ATTACK",
    "MOVE_FORWARD",
    "MOVE_BACKWARD",
    "TURN_LEFT",
    "TURN_RIGHT",
)

# Degrees of tolerance before we consider the player "facing" a target.
# Empirically confirmed on this build: TURN_LEFT increases ANGLE, TURN_RIGHT
# decreases it, and facing vector is (cos(angle), sin(angle)) in degrees.
_TURN_EPSILON_DEG = 10.0


@dataclass(frozen=True)
class ExecutionContext:
    player_pos: Point
    player_angle: float
    nearest_enemy: Optional[Point]
    nearest_health: Optional[Point]
    nearest_ammo: Optional[Point]


def _empty_buttons() -> Dict[str, int]:
    return {name: 0 for name in BUTTON_NAMES}


def _angle_diff_deg(target_angle: float, player_angle: float) -> float:
    """Signed difference in (-180, 180] degrees: positive means turn left."""
    return (target_angle - player_angle + 180.0) % 360.0 - 180.0


def _turn_toward(buttons: Dict[str, int], player_pos: Point, player_angle: float, target: Point) -> None:
    tx, ty = target
    px, py = player_pos
    target_angle = math.degrees(math.atan2(ty - py, tx - px)) % 360.0
    diff = _angle_diff_deg(target_angle, player_angle)
    if diff > _TURN_EPSILON_DEG:
        buttons["TURN_LEFT"] = 1
    elif diff < -_TURN_EPSILON_DEG:
        buttons["TURN_RIGHT"] = 1


def compute_buttons(action: Action, ctx: ExecutionContext) -> Dict[str, int]:
    buttons = _empty_buttons()

    if action == Action.WAIT:
        return buttons

    if action == Action.EXPLORE:
        # Fixed deterministic patrol: always move forward while veering
        # right, tracing an outward spiral instead of a straight line into
        # the nearest wall.
        buttons["MOVE_FORWARD"] = 1
        buttons["TURN_RIGHT"] = 1
        return buttons

    if action == Action.ATTACK:
        if ctx.nearest_enemy is not None:
            _turn_toward(buttons, ctx.player_pos, ctx.player_angle, ctx.nearest_enemy)
        buttons["ATTACK"] = 1
        return buttons

    if action == Action.FLEE:
        if ctx.nearest_enemy is not None:
            px, py = ctx.player_pos
            ex, ey = ctx.nearest_enemy
            away_point = (px + (px - ex), py + (py - ey))
            _turn_toward(buttons, ctx.player_pos, ctx.player_angle, away_point)
            buttons["MOVE_FORWARD"] = 1
        else:
            buttons["MOVE_BACKWARD"] = 1
        return buttons

    if action == Action.SEEK_HEALTH:
        buttons["MOVE_FORWARD"] = 1
        if ctx.nearest_health is not None:
            _turn_toward(buttons, ctx.player_pos, ctx.player_angle, ctx.nearest_health)
        return buttons

    if action == Action.SEEK_AMMO:
        buttons["MOVE_FORWARD"] = 1
        if ctx.nearest_ammo is not None:
            _turn_toward(buttons, ctx.player_pos, ctx.player_angle, ctx.nearest_ammo)
        return buttons

    raise ValueError(f"Unhandled action: {action!r}")
