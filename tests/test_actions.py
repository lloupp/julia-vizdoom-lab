from decision.actions import ACTION_DESCRIPTIONS, ALL_ACTIONS, Action


def test_all_six_actions_present():
    assert set(ALL_ACTIONS) == {
        Action.ATTACK,
        Action.FLEE,
        Action.SEEK_HEALTH,
        Action.SEEK_AMMO,
        Action.EXPLORE,
        Action.WAIT,
    }
    assert len(ALL_ACTIONS) == 6


def test_every_action_has_a_description():
    for action in ALL_ACTIONS:
        assert action in ACTION_DESCRIPTIONS
        assert isinstance(ACTION_DESCRIPTIONS[action], str)
        assert len(ACTION_DESCRIPTIONS[action]) > 0


def test_action_values_are_the_portuguese_names():
    assert Action.ATTACK.value == "atacar"
    assert Action.FLEE.value == "fugir"
    assert Action.SEEK_HEALTH.value == "buscar_vida"
    assert Action.SEEK_AMMO.value == "buscar_municao"
    assert Action.EXPLORE.value == "explorar"
    assert Action.WAIT.value == "esperar"
