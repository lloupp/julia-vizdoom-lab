from decision.state import GameState


def test_as_dict_round_trip():
    state = GameState(
        health=42.5, ammo=7, enemies_visible=2, enemy_distance=123.4,
        medkit_visible=True, ammo_visible=False,
    )
    d = state.as_dict()
    assert d == {
        "health": 42.5,
        "ammo": 7,
        "enemies_visible": 2,
        "enemy_distance": 123.4,
        "medkit_visible": True,
        "ammo_visible": False,
    }


def test_coarse_signature_only_absorbs_float_noise_not_real_progress():
    # Sub-unit float noise (e.g. from engine rounding) must not look like a change.
    a = GameState(health=81.0, ammo=3, enemies_visible=1, enemy_distance=205.1, medkit_visible=False, ammo_visible=False)
    b = GameState(health=81.4, ammo=3, enemies_visible=1, enemy_distance=205.4, medkit_visible=False, ammo_visible=False)
    assert a.coarse_signature() == b.coarse_signature()

    # But real combat progress (ammo spent, distance closing) must be visible,
    # so a sustained ATTACK is never mistaken for a stuck loop.
    c = GameState(health=81, ammo=2, enemies_visible=1, enemy_distance=212, medkit_visible=False, ammo_visible=False)
    assert a.coarse_signature() != c.coarse_signature()


def test_coarse_signature_distinguishes_different_states():
    a = GameState(health=81, ammo=3, enemies_visible=1, enemy_distance=205, medkit_visible=False, ammo_visible=False)
    b = GameState(health=20, ammo=3, enemies_visible=1, enemy_distance=205, medkit_visible=False, ammo_visible=False)
    assert a.coarse_signature() != b.coarse_signature()


def test_coarse_signature_handles_no_enemy():
    state = GameState(health=100, ammo=50, enemies_visible=0, enemy_distance=None, medkit_visible=False, ammo_visible=False)
    assert state.coarse_signature()[3] is None
