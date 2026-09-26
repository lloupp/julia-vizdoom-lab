from decision.actions import ALL_ACTIONS, Action
from decision.agents.base import Decision, DecisionAgent
from decision.agents.fallback import JuliaWithFallbackAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.state import GameState


class StubJuliaAgent(DecisionAgent):
    """Returns a fixed, pre-programmed Decision -- no real model involved."""

    name = "julia"

    def __init__(self, decision: Decision):
        self._decision = decision

    def decide(self, state, available_actions):
        return self._decision


STATE = GameState(
    health=100.0,
    ammo=50,
    enemies_visible=1,
    enemy_distance=100,
    medkit_visible=False,
    ammo_visible=False,
)


def test_uses_julia_choice_when_confident():
    stub = StubJuliaAgent(
        Decision(action=Action.ATTACK, confidence=0.9, source="julia", model_confidence=0.9)
    )
    agent = JuliaWithFallbackAgent(stub, RuleBasedAgent(), confidence_threshold=0.6)
    decision = agent.decide(STATE, ALL_ACTIONS)
    assert decision.action == Action.ATTACK
    assert decision.fallback_used is False
    assert decision.model_confidence == 0.9


def test_falls_back_to_rules_below_threshold():
    stub = StubJuliaAgent(
        Decision(action=Action.WAIT, confidence=0.2, source="julia", model_confidence=0.2)
    )
    agent = JuliaWithFallbackAgent(stub, RuleBasedAgent(), confidence_threshold=0.6)
    decision = agent.decide(STATE, ALL_ACTIONS)
    # RuleBasedAgent would choose ATTACK given an armed player facing an enemy.
    assert decision.action == Action.ATTACK
    assert decision.fallback_used is True
    assert decision.model_confidence == 0.2  # Julia's own confidence is preserved


def test_falls_back_to_rules_on_julia_error():
    stub = StubJuliaAgent(
        Decision(
            action=Action.WAIT,
            confidence=0.0,
            source="julia",
            model_confidence=0.0,
            error="RuntimeError: boom",
        )
    )
    agent = JuliaWithFallbackAgent(stub, RuleBasedAgent(), confidence_threshold=0.6)
    decision = agent.decide(STATE, ALL_ACTIONS)
    assert decision.fallback_used is True
    assert decision.error == "RuntimeError: boom"


def test_threshold_is_configurable():
    stub = StubJuliaAgent(
        Decision(action=Action.EXPLORE, confidence=0.5, source="julia", model_confidence=0.5)
    )
    lenient = JuliaWithFallbackAgent(stub, RuleBasedAgent(), confidence_threshold=0.4)
    strict = JuliaWithFallbackAgent(stub, RuleBasedAgent(), confidence_threshold=0.6)

    assert lenient.decide(STATE, ALL_ACTIONS).fallback_used is False
    assert strict.decide(STATE, ALL_ACTIONS).fallback_used is True
