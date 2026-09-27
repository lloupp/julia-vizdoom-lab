from __future__ import annotations

import sys
import types

from decision.actions import Action
from decision.state import GameState
from round3.agent import Round3ModelAgent, event_signature
from round3.backends import BackendBatch, DecisionBackend, LayaBackend
from round3.hierarchy import decide_hierarchically
from round3.prompts import build_model_state, ordered_actions


class FakeBackend(DecisionBackend):
    name = "fake"
    noul_is_calibrated = True

    def __init__(self, booleans=None, choice=Action.EXPLORE):
        self.booleans = booleans or {
            "survival_priority": 0.0,
            "engage_enemy": 0.0,
            "seek_health": 0.0,
            "seek_ammo": 0.0,
        }
        self.choice = choice
        self.calls = []

    def predict(self, state, questions):
        self.calls.append((state, questions))
        if set(questions) == {
            "survival_priority", "engage_enemy", "seek_health", "seek_ammo"
        }:
            answers = {
                key: {
                    "type": "noul",
                    "noul": value,
                    "probabilities": {"false": 1.0 - value, "true": value},
                }
                for key, value in self.booleans.items()
            }
        else:
            criteria = questions["action"]["criteria"]
            chosen = self.choice.value if self.choice.value in criteria else next(iter(criteria))
            answers = {
                "action": {
                    "type": "choice",
                    "choice": chosen,
                    "confidence": 0.8,
                    "probabilities": {
                        key: (0.8 if key == chosen else 0.2 / max(1, len(criteria) - 1))
                        for key in criteria
                    },
                }
            }
        return BackendBatch(answers=answers, latency_ms=10.0, metadata={"backend": "fake"})

    def choice_score(self, answer):
        return float(answer["confidence"]), "calibrated_confidence", True


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


def test_model_state_uses_fixed_canonical_action_order():
    supplied = [Action.WAIT, Action.ATTACK, Action.EXPLORE]
    payload = build_model_state(state(), supplied)
    ids = [item["id"] for item in payload["available_actions"]]
    assert ids == [a.value for a in ordered_actions(supplied)]
    assert ids == ["atacar", "explorar", "esperar"]


def test_survival_noul_narrows_before_choice():
    backend = FakeBackend(
        booleans={
            "survival_priority": 0.95,
            "engage_enemy": 0.9,
            "seek_health": 0.0,
            "seek_ammo": 0.0,
        }
    )
    result = decide_hierarchically(
        backend,
        state(health=15),
        [Action.ATTACK, Action.FLEE, Action.EXPLORE],
    )
    assert result.action == Action.FLEE
    assert result.stage == "survival:forced"
    assert result.model_calls == 1


def test_resource_choice_uses_second_small_choice_call():
    backend = FakeBackend(
        booleans={
            "survival_priority": 0.0,
            "engage_enemy": 0.0,
            "seek_health": 0.9,
            "seek_ammo": 0.9,
        },
        choice=Action.SEEK_AMMO,
    )
    result = decide_hierarchically(
        backend,
        state(enemies_visible=0, enemy_distance=None, medkit_visible=True, ammo_visible=True),
        [Action.SEEK_HEALTH, Action.SEEK_AMMO, Action.EXPLORE, Action.WAIT],
    )
    assert result.action == Action.SEEK_AMMO
    assert result.stage == "resource"
    assert result.model_calls == 2
    criteria = backend.calls[-1][1]["action"]["criteria"]
    assert list(criteria) == ["buscar_vida", "buscar_municao"]


def test_event_cache_avoids_repeated_model_calls_until_ttl():
    backend = FakeBackend(choice=Action.EXPLORE)
    agent = Round3ModelAgent(backend, max_hold_steps=2)
    s = state(enemies_visible=0, enemy_distance=None)
    actions = [Action.EXPLORE, Action.WAIT]

    first = agent.decide(s, actions)
    calls_after_first = len(backend.calls)
    second = agent.decide(s, actions)
    third = agent.decide(s, actions)

    assert first.action == Action.EXPLORE
    assert second.action == Action.EXPLORE
    assert third.action == Action.EXPLORE
    assert len(backend.calls) == calls_after_first
    assert agent.last_trace["cache_hit"] is True

    agent.decide(s, actions)
    assert len(backend.calls) > calls_after_first


def test_event_signature_changes_on_strategic_band_change():
    actions = [Action.EXPLORE, Action.WAIT]
    assert event_signature(state(health=80), actions) != event_signature(state(health=20), actions)


def test_laya_backend_forces_typed_decisions_router(monkeypatch):
    seen = {}

    class FakeRouter:
        def __init__(self, preload=False):
            seen["preload"] = preload

        def predict(self, state, questions, **kwargs):
            seen.update(kwargs)
            return {
                "answers": {
                    "x": {
                        "type": "noul",
                        "noul": 0.7,
                        "probabilities": {"false": 0.3, "true": 0.7},
                    }
                },
                "routing": {"model": kwargs.get("model")},
            }

    fake_module = types.SimpleNamespace(Router=FakeRouter)
    monkeypatch.setitem(sys.modules, "laya", fake_module)

    backend = LayaBackend()
    batch = backend.predict(
        {"body": "state"},
        {"x": {"type": "noul", "instructions": "test"}},
    )
    assert seen["model"] == "typed-decisions"
    assert seen["max_len"] == 1024
    assert batch.metadata["routing"]["model"] == "typed-decisions"
