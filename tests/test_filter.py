from decision.actions import Action
from decision.agents.base import Decision, DecisionAgent
from decision.agents.filter import ActionFilterGuard, filter_actions
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


class StubAgent(DecisionAgent):
    """Records the available_actions it was called with; always picks the first."""

    name = "stub"

    def __init__(self):
        self.last_available = None

    def decide(self, state, available_actions):
        self.last_available = list(available_actions)
        return Decision(action=available_actions[0], confidence=0.9, source=self.name)


def test_no_ammo_never_offers_attack():
    state = make_state(ammo=0, enemies_visible=1, enemy_distance=50)
    available = [Action.ATTACK, Action.FLEE, Action.EXPLORE, Action.WAIT]
    filtered = filter_actions(state, available)
    assert Action.ATTACK not in filtered


def test_critical_health_narrows_to_survival_options():
    state = make_state(health=10.0, medkit_visible=True, enemies_visible=1, enemy_distance=80)
    available = [Action.ATTACK, Action.FLEE, Action.SEEK_HEALTH, Action.EXPLORE, Action.WAIT]
    filtered = filter_actions(state, available)
    assert set(filtered) == {Action.FLEE, Action.SEEK_HEALTH}
    assert Action.ATTACK not in filtered
    assert Action.EXPLORE not in filtered
    assert Action.WAIT not in filtered


def test_critical_health_with_no_survival_option_falls_through_to_other_rules():
    # Neither SEEK_HEALTH nor FLEE is on the table (no medkit, no enemy), so
    # the critical-health rule is a no-op here -- but with nothing visible,
    # the no-danger-or-goal rule still applies and drops WAIT.
    state = make_state(health=10.0, medkit_visible=False, enemies_visible=0)
    available = [Action.EXPLORE, Action.WAIT]
    filtered = filter_actions(state, available)
    assert filtered == [Action.EXPLORE]


def test_no_danger_or_goal_drops_wait():
    state = make_state()  # nothing visible
    available = [Action.EXPLORE, Action.WAIT]
    filtered = filter_actions(state, available)
    assert filtered == [Action.EXPLORE]


def test_preserves_input_order():
    state = make_state(ammo=0, enemies_visible=1, enemy_distance=50)
    available = [Action.WAIT, Action.EXPLORE, Action.FLEE, Action.ATTACK]
    filtered = filter_actions(state, available)
    assert filtered == [Action.WAIT, Action.EXPLORE, Action.FLEE]


def test_never_introduces_an_action_not_in_available():
    state = make_state(health=5.0, medkit_visible=True)
    available = [Action.SEEK_HEALTH, Action.WAIT]  # FLEE not offered
    filtered = filter_actions(state, available)
    assert Action.FLEE not in filtered
    assert set(filtered) <= set(available)


def test_guard_delegates_to_wrapped_agent_with_filtered_set():
    stub = StubAgent()
    guard = ActionFilterGuard(stub, filter_fn=filter_actions)
    state = make_state(ammo=0, enemies_visible=1, enemy_distance=50)
    available = [Action.ATTACK, Action.FLEE, Action.EXPLORE, Action.WAIT]

    decision = guard.decide(state, available)

    assert Action.ATTACK not in stub.last_available
    assert decision.offered_actions == stub.last_available
    assert not decision.source.endswith(":forced")


def test_guard_short_circuits_without_calling_agent_when_only_one_action_left():
    stub = StubAgent()
    guard = ActionFilterGuard(stub, filter_fn=filter_actions)
    state = make_state()  # nothing visible -> WAIT dropped -> only EXPLORE left
    available = [Action.EXPLORE, Action.WAIT]

    decision = guard.decide(state, available)

    assert stub.last_available is None  # the wrapped agent was never called
    assert decision.action == Action.EXPLORE
    assert decision.offered_actions == [Action.EXPLORE]
    assert decision.source.endswith(":forced")


def test_guard_never_narrows_further_than_the_filter_did():
    stub = StubAgent()
    guard = ActionFilterGuard(stub, filter_fn=filter_actions)
    state = make_state(health=10.0, medkit_visible=True, enemies_visible=1, enemy_distance=80)
    available = [Action.ATTACK, Action.FLEE, Action.SEEK_HEALTH, Action.EXPLORE, Action.WAIT]

    guard.decide(state, available)

    assert set(stub.last_available) == {Action.FLEE, Action.SEEK_HEALTH}
