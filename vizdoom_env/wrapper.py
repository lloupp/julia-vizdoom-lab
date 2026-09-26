"""VizDoom backend: extracts the minimal GameState and runs the executor.

Scenario: the deathmatch.wad bundled with the vizdoom package (map01). It
was chosen over the other bundled scenarios because it is the only one that
simultaneously has monsters, health items (Stimpack/Medikit/HealthBonus) and
ammo items (ClipBox/ShellBox/RocketBox) with free player movement, matching
every field of our minimal state.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import vizdoom as vzd

from decision.actions import ALL_ACTIONS, Action
from decision.state import GameState
from vizdoom_env.executor import BUTTON_NAMES, ExecutionContext, compute_buttons

Point = Tuple[float, float]

_GAME_VARIABLES = [
    vzd.GameVariable.HEALTH,
    vzd.GameVariable.SELECTED_WEAPON,
    vzd.GameVariable.SELECTED_WEAPON_AMMO,
    vzd.GameVariable.KILLCOUNT,
    vzd.GameVariable.DAMAGE_TAKEN,
    vzd.GameVariable.POSITION_X,
    vzd.GameVariable.POSITION_Y,
    vzd.GameVariable.ANGLE,
]

_BUTTON_ENUM = {
    "ATTACK": vzd.Button.ATTACK,
    "MOVE_FORWARD": vzd.Button.MOVE_FORWARD,
    "MOVE_BACKWARD": vzd.Button.MOVE_BACKWARD,
    "TURN_LEFT": vzd.Button.TURN_LEFT,
    "TURN_RIGHT": vzd.Button.TURN_RIGHT,
}

_ENEMY_CATEGORY = "Monster"
_HEALTH_CATEGORY = "Health"
_AMMO_CATEGORY = "Ammo"

# Item pickups sit close to the floor; visibility beyond this range is not
# actionable for our simple "move toward it" executor, so we cap it. Chosen
# generously relative to the map's corridor scale (~700 map units wide).
_MAX_ITEM_SIGHT_RANGE = 900.0


@dataclass(frozen=True)
class _Scalars:
    health: float
    ammo: int
    selected_weapon: float
    kills: int
    damage_taken: float
    pos: Point
    angle: float


def _nearest(points: List[Point], origin: Point) -> Optional[Tuple[Point, float]]:
    if not points:
        return None
    best_point, best_dist = None, math.inf
    for p in points:
        dist = math.hypot(p[0] - origin[0], p[1] - origin[1])
        if dist < best_dist:
            best_point, best_dist = p, dist
    return best_point, best_dist


class VizDoomEnv:
    def __init__(
        self,
        frame_skip: int = 10,
        episode_timeout: int = 2100,
        window_visible: bool = False,
        seed: Optional[int] = None,
    ) -> None:
        self.frame_skip = frame_skip
        self.game = vzd.DoomGame()
        scenario_dir = os.path.join(os.path.dirname(vzd.__file__), "scenarios")
        self.game.set_doom_scenario_path(os.path.join(scenario_dir, "deathmatch.wad"))
        self.game.set_doom_map("map01")
        self.game.set_screen_resolution(vzd.ScreenResolution.RES_320X240)
        self.game.set_screen_format(vzd.ScreenFormat.CRCGCB)
        self.game.set_render_hud(False)
        self.game.set_sound_enabled(False)
        self.game.set_labels_buffer_enabled(True)
        self.game.set_available_game_variables(_GAME_VARIABLES)
        self.game.set_available_buttons([_BUTTON_ENUM[name] for name in BUTTON_NAMES])
        self.game.set_episode_timeout(episode_timeout)
        self.game.set_window_visible(window_visible)
        self.game.set_mode(vzd.Mode.PLAYER)
        if seed is not None:
            self.game.set_seed(seed)
        self.game.init()

        self._prev_ammo = 0
        self._prev_weapon = None
        self._ammo_consumed_total = 0
        self._tics_elapsed = 0

    def close(self) -> None:
        self.game.close()

    def reset(self) -> GameState:
        self.game.new_episode()
        self._ammo_consumed_total = 0
        self._tics_elapsed = 0
        scalars = self._read_scalars()
        self._prev_ammo = scalars.ammo
        self._prev_weapon = scalars.selected_weapon
        enemies, healths, ammos = self._read_labels()
        return self._build_state(scalars, enemies, healths, ammos)

    def compute_available_actions(self, state: GameState) -> List[Action]:
        available = {Action.EXPLORE, Action.WAIT}
        if state.enemies_visible > 0 and state.ammo > 0:
            available.add(Action.ATTACK)
        if state.enemies_visible > 0:
            available.add(Action.FLEE)
        if state.medkit_visible:
            available.add(Action.SEEK_HEALTH)
        if state.ammo_visible:
            available.add(Action.SEEK_AMMO)
        return [a for a in ALL_ACTIONS if a in available]

    def step(self, action: Action) -> Tuple[Optional[GameState], bool, Dict]:
        """Run the action's macro for ``frame_skip`` tics.

        Returns (state, done, info). ``state`` is None when the episode
        finished mid-macro (death or timeout), since VizDoom no longer
        exposes labels/state at that point.
        """
        for _ in range(self.frame_skip):
            if self.game.is_episode_finished():
                break
            scalars = self._read_scalars()
            enemies, healths, ammos = self._read_labels()
            ctx = self._build_context(scalars, enemies, healths, ammos)
            buttons_map = compute_buttons(action, ctx)
            button_vector = [buttons_map[name] for name in BUTTON_NAMES]
            self.game.make_action(button_vector, 1)
            self._tics_elapsed += 1
            self._track_ammo_consumption()

        info = {
            "kills": int(self.game.get_game_variable(vzd.GameVariable.KILLCOUNT)),
            "damage_taken": float(self.game.get_game_variable(vzd.GameVariable.DAMAGE_TAKEN)),
            "ammo_consumed_total": self._ammo_consumed_total,
            "tics_elapsed": self._tics_elapsed,
        }

        if self.game.is_episode_finished():
            return None, True, info

        scalars = self._read_scalars()
        enemies, healths, ammos = self._read_labels()
        state = self._build_state(scalars, enemies, healths, ammos)
        return state, False, info

    def _track_ammo_consumption(self) -> None:
        ammo_now = int(self.game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON_AMMO))
        weapon_now = float(self.game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON))
        # Doom auto-equips a newly picked-up weapon; SELECTED_WEAPON_AMMO then
        # jumps to that weapon's own ammo pool, which is not consumption. Only
        # count a drop as "spent" when the equipped weapon didn't change.
        if weapon_now == self._prev_weapon:
            delta = ammo_now - self._prev_ammo
            if delta < 0:
                self._ammo_consumed_total += -delta
        self._prev_ammo = ammo_now
        self._prev_weapon = weapon_now

    def _read_scalars(self) -> _Scalars:
        g = self.game
        return _Scalars(
            health=float(g.get_game_variable(vzd.GameVariable.HEALTH)),
            ammo=int(g.get_game_variable(vzd.GameVariable.SELECTED_WEAPON_AMMO)),
            selected_weapon=float(g.get_game_variable(vzd.GameVariable.SELECTED_WEAPON)),
            kills=int(g.get_game_variable(vzd.GameVariable.KILLCOUNT)),
            damage_taken=float(g.get_game_variable(vzd.GameVariable.DAMAGE_TAKEN)),
            pos=(
                float(g.get_game_variable(vzd.GameVariable.POSITION_X)),
                float(g.get_game_variable(vzd.GameVariable.POSITION_Y)),
            ),
            angle=float(g.get_game_variable(vzd.GameVariable.ANGLE)),
        )

    def _read_labels(self) -> Tuple[List[Point], List[Point], List[Point]]:
        state = self.game.get_state()
        enemies: List[Point] = []
        healths: List[Point] = []
        ammos: List[Point] = []
        if state is None or state.labels is None:
            return enemies, healths, ammos
        for label in state.labels:
            category = str(label.object_category)
            pos = (label.object_position_x, label.object_position_y)
            if category == _ENEMY_CATEGORY:
                enemies.append(pos)
            elif category == _HEALTH_CATEGORY:
                healths.append(pos)
            elif category == _AMMO_CATEGORY:
                ammos.append(pos)
        return enemies, healths, ammos

    def _build_context(
        self,
        scalars: _Scalars,
        enemies: List[Point],
        healths: List[Point],
        ammos: List[Point],
    ) -> ExecutionContext:
        nearest_enemy = _nearest(enemies, scalars.pos)
        nearest_health = _nearest(healths, scalars.pos)
        nearest_ammo = _nearest(ammos, scalars.pos)
        return ExecutionContext(
            player_pos=scalars.pos,
            player_angle=scalars.angle,
            nearest_enemy=nearest_enemy[0] if nearest_enemy else None,
            nearest_health=nearest_health[0] if nearest_health else None,
            nearest_ammo=nearest_ammo[0] if nearest_ammo else None,
        )

    def _build_state(
        self,
        scalars: _Scalars,
        enemies: List[Point],
        healths: List[Point],
        ammos: List[Point],
    ) -> GameState:
        nearest_enemy = _nearest(enemies, scalars.pos)
        enemy_distance = None
        if nearest_enemy is not None and nearest_enemy[1] <= _MAX_ITEM_SIGHT_RANGE:
            enemy_distance = nearest_enemy[1]

        def _within_range(points: List[Point]) -> bool:
            return any(math.hypot(p[0] - scalars.pos[0], p[1] - scalars.pos[1]) <= _MAX_ITEM_SIGHT_RANGE for p in points)

        medkit_visible = _within_range(healths)
        ammo_visible = _within_range(ammos)
        return GameState(
            health=scalars.health,
            ammo=scalars.ammo,
            enemies_visible=len(enemies),
            enemy_distance=enemy_distance,
            medkit_visible=medkit_visible,
            ammo_visible=ammo_visible,
        )
