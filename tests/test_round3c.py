from __future__ import annotations

from decision.actions import Action
from decision.state import GameState
from round3.backends import BackendBatch, DecisionBackend
from round3c.agent import DirectChoiceAgent


class FakeBackend(DecisionBackend):
    name = "fake"

    def __init__(self, choice: Action = Action.EXPLORE):
        self.choice = choice
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((state, questions))
        criteria = questions["action"]["criteria"]
        chosen = self.choice.value if self.choice.value in criteria else next(iter(criteria))
        probability = 0.8
        rest = (1.0 - probability) / max(1, len(criteria) - 1)
        return BackendBatch(
            answers={
                "action": {
                    "type": "choice",
                    "choice": chosen,
                    "confidence": probability,
                    "probabilities": {
                        key: probability if key == chosen else rest
                        for key in criteria
                    },
                }
            },
            latency_ms=12.0,
            metadata={"backend": "fake"},
        )

    def choice_score(self, answer):
        return float(answer["confidence"]), "confidence", True


def state(**overrides):
    values = dict(
        health=80,
        ammo=20,
        enemies_visible=1,
        enemy_distance=250,
        medkit_visible=False,
        ammo_visible=False,
    )
    values.update(overrides)
    return GameState(**values)


def test_direct_choice_uses_exactly_one_choice_question():
    backend = FakeBackend(Action.ATTACK)
    agent = DirectChoiceAgent(backend)

    decision = agent.decide(
        state(),
        [Action.WAIT, Action.EXPLORE, Action.ATTACK],
    )

    assert decision.action == Action.ATTACK
    assert len(backend.calls) == 1
    questions = backend.calls[0][1]
    assert list(questions) == ["action"]
    assert questions["action"]["type"] == "choice"
    assert list(questions["action"]["criteria"]) == [
        "atacar",
        "explorar",
        "esperar",
    ]
    assert agent.last_trace["stage"] == "direct_choice"
    assert agent.last_trace["model_calls"] == 1


def test_direct_choice_contains_no_boolean_gate():
    backend = FakeBackend(Action.FLEE)
    agent = DirectChoiceAgent(backend)

    agent.decide(
        state(health=10),
        [Action.ATTACK, Action.FLEE, Action.EXPLORE],
    )

    questions = backend.calls[0][1]
    assert all(question["type"] == "choice" for question in questions.values())
    assert "survival_priority" not in questions
    assert "engage_enemy" not in questions


def test_single_valid_action_does_not_call_model():
    backend = FakeBackend()
    agent = DirectChoiceAgent(backend)

    decision = agent.decide(state(), [Action.EXPLORE])

    assert decision.action == Action.EXPLORE
    assert backend.calls == []
    assert agent.last_trace["stage"] == "single_valid_action"
    assert agent.last_trace["model_calls"] == 0


def test_event_cache_reuses_choice_until_ttl():
    backend = FakeBackend(Action.EXPLORE)
    agent = DirectChoiceAgent(backend, max_hold_steps=2)
    s = state(enemies_visible=0, enemy_distance=None)
    actions = [Action.EXPLORE, Action.WAIT]

    first = agent.decide(s, actions)
    second = agent.decide(s, actions)
    third = agent.decide(s, actions)

    assert first.action == Action.EXPLORE
    assert second.action == Action.EXPLORE
    assert third.action == Action.EXPLORE
    assert len(backend.calls) == 1

    agent.decide(s, actions)
    assert len(backend.calls) == 2


def test_error_falls_back_to_rules_only_on_failure():
    class BrokenBackend(FakeBackend):
        def predict(self, state, questions):
            raise RuntimeError("boom")

    agent = DirectChoiceAgent(BrokenBackend())
    decision = agent.decide(
        state(),
        [Action.ATTACK, Action.FLEE, Action.EXPLORE],
    )

    assert decision.fallback_used is True
    assert decision.error == "RuntimeError: boom"
    assert agent.last_trace["stage"] == "error_fallback"
