from decision.actions import ALL_ACTIONS, Action
from decision.agents.rule_based import RuleBasedAgent
from decision.state import GameState


def make_state(**overrides):
    defaults = dict(
        health=100.0,
        ammo=50,
        enemies_visible=0,
        enemy_distance=None,
        medkit_visible=False,
        ammo_visible=False,
    )
    defaults.update(overrides)
    return GameState(**defaults)


def test_attacks_when_enemy_visible_and_armed():
    agent = RuleBasedAgent()
    state = make_state(enemies_visible=1, enemy_distance=200)
    decision = agent.decide(state, ALL_ACTIONS)
    assert decision.action == Action.ATTACK
    assert decision.confidence == 1.0


def test_flees_when_out_of_ammo_and_enemy_visible():
    agent = RuleBasedAgent()
    state = make_state(ammo=0, enemies_visible=1, enemy_distance=100)
    decision = agent.decide(state, ALL_ACTIONS)
    assert decision.action == Action.FLEE


def test_seeks_ammo_when_out_of_ammo_and_ammo_visible():
    agent = RuleBasedAgent()
    state = make_state(ammo=0, ammo_visible=True)
    decision = agent.decide(state, ALL_ACTIONS)
    assert decision.action == Action.SEEK_AMMO


def test_seeks_health_when_low_health_and_medkit_visible():
    agent = RuleBasedAgent(low_health_threshold=35.0)
    state = make_state(health=20.0, medkit_visible=True)
    decision = agent.decide(state, ALL_ACTIONS)
    assert decision.action == Action.SEEK_HEALTH


def test_explores_with_no_signal():
    agent = RuleBasedAgent()
    state = make_state()
    decision = agent.decide(state, ALL_ACTIONS)
    assert decision.action == Action.EXPLORE


def test_never_picks_an_unavailable_action():
    agent = RuleBasedAgent()
    state = make_state(enemies_visible=1, enemy_distance=50)
    available = [Action.EXPLORE, Action.WAIT]  # ATTACK deliberately excluded
    decision = agent.decide(state, available)
    assert decision.action in available


def test_is_deterministic():
    agent = RuleBasedAgent()
    state = make_state(health=15.0, ammo=0, enemies_visible=1, enemy_distance=80)
    first = agent.decide(state, ALL_ACTIONS)
    second = agent.decide(state, ALL_ACTIONS)
    assert first.action == second.action
