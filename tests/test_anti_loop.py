from decision.actions import ALL_ACTIONS, Action
from decision.agents.anti_loop import AntiLoopGuard
from decision.agents.base import Decision, DecisionAgent
from decision.state import GameState


class StuckAgent(DecisionAgent):
    """Always picks the same action, simulating a stuck policy."""

    name = "stuck"

    def __init__(self, action: Action):
        self._action = action

    def decide(self, state, available_actions):
        return Decision(action=self._action, confidence=1.0, source=self.name)


STATE = GameState(
    health=100.0,
    ammo=50,
    enemies_visible=0,
    enemy_distance=None,
    medkit_visible=True,
    ammo_visible=False,
)


def test_breaks_loop_after_max_repeat_identical_state_and_action():
    guard = AntiLoopGuard(StuckAgent(Action.SEEK_HEALTH), max_repeat=4)

    decisions = [guard.decide(STATE, ALL_ACTIONS) for _ in range(4)]

    assert [d.action for d in decisions[:3]] == [Action.SEEK_HEALTH] * 3
    assert decisions[3].action != Action.SEEK_HEALTH
    assert decisions[3].antiloop_override is True
    assert decisions[3].fallback_used is False
    assert decisions[3].source.endswith("+antiloop")


def test_does_not_trigger_when_state_changes():
    guard = AntiLoopGuard(StuckAgent(Action.SEEK_HEALTH), max_repeat=3)
    changing_state = STATE
    other_state = GameState(
        health=90.0, ammo=50, enemies_visible=0, enemy_distance=None,
        medkit_visible=True, ammo_visible=False,
    )

    d1 = guard.decide(changing_state, ALL_ACTIONS)
    d2 = guard.decide(other_state, ALL_ACTIONS)
    d3 = guard.decide(changing_state, ALL_ACTIONS)

    assert [d1.action, d2.action, d3.action] == [Action.SEEK_HEALTH] * 3


def test_does_not_trigger_before_max_repeat():
    guard = AntiLoopGuard(StuckAgent(Action.EXPLORE), max_repeat=5)
    decisions = [guard.decide(STATE, ALL_ACTIONS) for _ in range(4)]
    assert all(d.action == Action.EXPLORE for d in decisions)


def test_reset_clears_history():
    guard = AntiLoopGuard(StuckAgent(Action.SEEK_HEALTH), max_repeat=2)
    guard.decide(STATE, ALL_ACTIONS)
    guard.decide(STATE, ALL_ACTIONS)  # would trigger on the 3rd call
    guard.reset()
    decision = guard.decide(STATE, ALL_ACTIONS)
    assert decision.action == Action.SEEK_HEALTH


def test_override_records_which_action_it_replaced():
    guard = AntiLoopGuard(StuckAgent(Action.SEEK_HEALTH), max_repeat=3)
    decisions = [guard.decide(STATE, ALL_ACTIONS) for _ in range(3)]
    assert decisions[2].antiloop_override is True
    assert decisions[2].overridden_from == Action.SEEK_HEALTH
    assert decisions[0].overridden_from is None


def test_action_specific_limit_breaks_wait_loops_sooner():
    # General limit is generous (5), but WAIT gets a tighter leash (2), as
    # round 1 found Julia defaults to "esperar" far more than the baseline.
    guard = AntiLoopGuard(
        StuckAgent(Action.WAIT), max_repeat=5, action_max_repeat={Action.WAIT: 2}
    )
    decisions = [guard.decide(STATE, ALL_ACTIONS) for _ in range(2)]
    assert decisions[0].action == Action.WAIT
    assert decisions[1].action != Action.WAIT
    assert decisions[1].overridden_from == Action.WAIT


def test_action_specific_limit_does_not_tighten_other_actions():
    guard = AntiLoopGuard(
        StuckAgent(Action.EXPLORE), max_repeat=5, action_max_repeat={Action.WAIT: 2}
    )
    decisions = [guard.decide(STATE, ALL_ACTIONS) for _ in range(4)]
    assert all(d.action == Action.EXPLORE for d in decisions)
