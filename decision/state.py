"""Minimal, engine-agnostic game state consumed by the decision layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GameState:
    """Minimal state shared by every agent and every game backend.

    Fields are intentionally generic (no VizDoom-specific units) so the same
    ``GameState`` shape can be produced by a different game (e.g. Minecraft)
    without changing anything in ``decision/``.
    """

    health: float
    ammo: int
    enemies_visible: int
    enemy_distance: Optional[float]
    medkit_visible: bool
    ammo_visible: bool

    def as_dict(self) -> dict:
        return {
            "health": self.health,
            "ammo": self.ammo,
            "enemies_visible": self.enemies_visible,
            "enemy_distance": self.enemy_distance,
            "medkit_visible": self.medkit_visible,
            "ammo_visible": self.ammo_visible,
        }

    def coarse_signature(self) -> tuple:
        """View of the state used to detect "nothing is changing" loops.

        Only rounds off float noise (health/distance to whole units); it must
        NOT bucket ammo or distance coarsely, or a legitimate sustained
        ATTACK (ammo ticking down, distance slowly closing) gets misread as a
        stuck loop and gets interrupted mid-fight.
        """
        return (
            round(self.health),
            self.ammo,
            self.enemies_visible,
            None if self.enemy_distance is None else round(self.enemy_distance),
            self.medkit_visible,
            self.ammo_visible,
        )
