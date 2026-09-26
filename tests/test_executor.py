from decision.actions import Action
from vizdoom_env.executor import ExecutionContext, compute_buttons


def test_wait_presses_nothing():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.WAIT, ctx)
    assert all(v == 0 for v in buttons.values())


def test_explore_always_moves_forward_and_turns_right():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.EXPLORE, ctx)
    assert buttons["MOVE_FORWARD"] == 1
    assert buttons["TURN_RIGHT"] == 1
    assert buttons["ATTACK"] == 0


def test_attack_presses_attack_even_without_target():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.ATTACK, ctx)
    assert buttons["ATTACK"] == 1


def test_attack_turns_left_toward_enemy_ahead_and_left():
    # Player facing east (angle 0); enemy directly north-ish (90 deg) is to the left.
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=(0, 10), nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.ATTACK, ctx)
    assert buttons["TURN_LEFT"] == 1
    assert buttons["TURN_RIGHT"] == 0
    assert buttons["ATTACK"] == 1


def test_attack_does_not_turn_when_already_aligned():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=(10, 0), nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.ATTACK, ctx)
    assert buttons["TURN_LEFT"] == 0
    assert buttons["TURN_RIGHT"] == 0


def test_flee_moves_backward_without_known_enemy_position():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.FLEE, ctx)
    assert buttons["MOVE_BACKWARD"] == 1
    assert buttons["MOVE_FORWARD"] == 0


def test_flee_turns_away_and_moves_forward_with_known_enemy():
    # Enemy to the east (10,0); fleeing means facing west and moving forward.
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=(10, 0), nearest_health=None, nearest_ammo=None)
    buttons = compute_buttons(Action.FLEE, ctx)
    assert buttons["MOVE_FORWARD"] == 1
    assert buttons["MOVE_BACKWARD"] == 0
    # Target angle away from enemy is 180 deg, player faces 0 deg -> must turn.
    assert buttons["TURN_LEFT"] == 1 or buttons["TURN_RIGHT"] == 1


def test_seek_health_moves_toward_target():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=(10, 0), nearest_ammo=None)
    buttons = compute_buttons(Action.SEEK_HEALTH, ctx)
    assert buttons["MOVE_FORWARD"] == 1
    assert buttons["TURN_LEFT"] == 0
    assert buttons["TURN_RIGHT"] == 0


def test_seek_ammo_moves_toward_target():
    ctx = ExecutionContext(player_pos=(0, 0), player_angle=0, nearest_enemy=None, nearest_health=None, nearest_ammo=(0, -10))
    buttons = compute_buttons(Action.SEEK_AMMO, ctx)
    assert buttons["MOVE_FORWARD"] == 1
    assert buttons["TURN_RIGHT"] == 1  # target is to the right/south of a player facing east


def test_is_a_pure_function():
    ctx = ExecutionContext(player_pos=(1, 2), player_angle=33, nearest_enemy=(5, 5), nearest_health=None, nearest_ammo=None)
    first = compute_buttons(Action.ATTACK, ctx)
    second = compute_buttons(Action.ATTACK, ctx)
    assert first == second
