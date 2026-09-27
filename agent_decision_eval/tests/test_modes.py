from agent_decision_eval.actions import ALL_ACTIONS, Action
from agent_decision_eval.models.base import DecisionModel, ModelDecision
from agent_decision_eval.modes import (
    SAFE_FALLBACK_ACTION,
    CategoryAccuracy,
    JuliaOnlyMode,
    LayaOnlyMode,
    ParallelMode,
    PrimaryFallbackMode,
)
from agent_decision_eval.tasks import Task

TASK = Task("t1", "some scenario", Action.READ)


class StubModel(DecisionModel):
    """Always returns a pre-programmed decision -- no real model involved."""

    def __init__(self, name: str, decision: ModelDecision):
        self.name = name
        self._decision = decision
        self.calls = 0

    def predict(self, task, options):
        self.calls += 1
        return self._decision


def decision(choice, max_probability=0.9, model_confidence=None, error=None):
    return ModelDecision(choice=choice, probabilities={}, max_probability=max_probability, model_confidence=model_confidence, error=error)


def test_laya_only_mode_uses_laya_choice_directly():
    laya = StubModel("laya", decision(Action.READ))
    mode = LayaOnlyMode(laya)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.READ
    assert result.source == "laya"
    assert result.julia is None


def test_julia_only_mode_uses_julia_choice_directly():
    julia = StubModel("julia", decision(Action.GREP))
    mode = JuliaOnlyMode(julia)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.GREP
    assert result.source == "julia"
    assert result.laya is None


def test_parallel_mode_agreement_uses_the_shared_choice():
    laya = StubModel("laya", decision(Action.READ, max_probability=0.6))
    julia = StubModel("julia", decision(Action.READ, max_probability=0.95))
    mode = ParallelMode(laya, julia, CategoryAccuracy())
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.READ
    assert result.divergence is False
    assert result.source == "agreement"
    # Must never combine the two probabilities arithmetically.
    assert result.final_action == Action.READ


def test_parallel_mode_divergence_on_sensitive_action_blocks_auto_execution():
    laya = StubModel("laya", decision(Action.WRITE, max_probability=0.99))
    julia = StubModel("julia", decision(Action.READ, max_probability=0.99))
    mode = ParallelMode(laya, julia, CategoryAccuracy())
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.divergence is True
    assert result.blocked_sensitive is True
    assert result.final_action == SAFE_FALLBACK_ACTION
    assert result.final_action not in (Action.WRITE, Action.EDIT, Action.BASH)


def test_parallel_mode_read_only_divergence_prefers_better_historical_model():
    laya = StubModel("laya", decision(Action.READ))
    julia = StubModel("julia", decision(Action.GREP))
    history = CategoryAccuracy(read_only_accuracy={"laya": 0.5, "julia": 0.9})
    mode = ParallelMode(laya, julia, history)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.divergence is True
    assert result.blocked_sensitive is False
    assert result.final_action == Action.GREP  # julia has the better read-only history
    assert result.source == "divergence:prefer_julia"


def test_parallel_mode_falls_back_to_overall_accuracy_when_read_only_tied():
    laya = StubModel("laya", decision(Action.READ))
    julia = StubModel("julia", decision(Action.GREP))
    history = CategoryAccuracy(
        read_only_accuracy={"laya": 0.8, "julia": 0.8},
        overall_accuracy={"laya": 0.6, "julia": 0.7},
    )
    mode = ParallelMode(laya, julia, history)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.GREP


def test_parallel_mode_deterministic_default_when_everything_tied():
    laya = StubModel("laya", decision(Action.READ))
    julia = StubModel("julia", decision(Action.GREP))
    mode = ParallelMode(laya, julia, CategoryAccuracy())  # no history at all
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.READ  # documented fixed default


def test_primary_fallback_uses_laya_when_confident():
    laya = StubModel("laya", decision(Action.READ, model_confidence=0.9))
    julia = StubModel("julia", decision(Action.GREP))
    mode = PrimaryFallbackMode(laya, julia, confidence_threshold=0.7)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.READ
    assert result.used_fallback is False
    assert julia.calls == 0  # never even called


def test_primary_fallback_uses_julia_below_threshold():
    laya = StubModel("laya", decision(Action.READ, model_confidence=0.3))
    julia = StubModel("julia", decision(Action.GREP))
    mode = PrimaryFallbackMode(laya, julia, confidence_threshold=0.7)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.final_action == Action.GREP
    assert result.used_fallback is True


def test_primary_fallback_falls_back_on_laya_error():
    laya = StubModel("laya", decision(Action.STOP, model_confidence=0.99, error="boom"))
    julia = StubModel("julia", decision(Action.READ))
    mode = PrimaryFallbackMode(laya, julia, confidence_threshold=0.5)
    result = mode.decide(TASK, ALL_ACTIONS)
    assert result.used_fallback is True
    assert result.final_action == Action.READ


def test_primary_fallback_threshold_is_configurable():
    laya = StubModel("laya", decision(Action.READ, model_confidence=0.6))
    julia = StubModel("julia", decision(Action.GREP))

    lenient = PrimaryFallbackMode(laya, julia, confidence_threshold=0.5)
    assert lenient.decide(TASK, ALL_ACTIONS).used_fallback is False

    strict = PrimaryFallbackMode(laya, julia, confidence_threshold=0.7)
    assert strict.decide(TASK, ALL_ACTIONS).used_fallback is True
