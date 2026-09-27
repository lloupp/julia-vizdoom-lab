from __future__ import annotations

import sys
import types

from round3b.backends import LayaRecommendedBackend


def test_laya_converts_noul_to_neutral_choice_and_normalizes(monkeypatch):
    seen = {}

    class FakeRouter:
        def __init__(self, preload=False):
            seen["preload"] = preload

        def predict(self, state, questions, **kwargs):
            seen["kwargs"] = kwargs
            seen["questions"] = questions
            return {
                "answers": {
                    "engage_enemy": {
                        "type": "choice",
                        "choice": "A",
                        "confidence": 0.77,
                        "probabilities": {"A": 0.77, "B": 0.23},
                    }
                },
                "routing": {
                    "model": "english",
                    "reason": "English detected",
                },
            }

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=FakeRouter))

    backend = LayaRecommendedBackend()
    batch = backend.predict(
        {"objective": "survive and fight"},
        {
            "engage_enemy": {
                "type": "noul",
                "instructions": "Should the agent attack?",
                "criteria": {
                    "false": "No, do not attack.",
                    "true": "Yes, attack now.",
                },
            }
        },
    )

    rendered = seen["questions"]["engage_enemy"]
    assert rendered["type"] == "choice"
    assert rendered["criteria"] == {
        "A": "Yes, attack now.",
        "B": "No, do not attack.",
    }
    assert seen["kwargs"] == {}

    answer = batch.answers["engage_enemy"]
    assert answer["type"] == "noul"
    assert answer["noul"] == 0.77
    assert answer["probabilities"] == {"false": 0.23, "true": 0.77}
    assert answer["source_type"] == "neutral_binary_choice"
    assert batch.metadata["routing"]["model"] == "english"


def test_laya_leaves_native_choice_unchanged(monkeypatch):
    seen = {}

    class FakeRouter:
        def __init__(self, preload=False):
            pass

        def predict(self, state, questions, **kwargs):
            seen["questions"] = questions
            return {
                "answers": {
                    "action": {
                        "type": "choice",
                        "choice": "explorar",
                        "confidence": 0.8,
                        "probabilities": {
                            "explorar": 0.8,
                            "esperar": 0.2,
                        },
                    }
                },
                "routing": {"model": "english"},
            }

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=FakeRouter))

    backend = LayaRecommendedBackend()
    batch = backend.predict(
        {"objective": "survive"},
        {
            "action": {
                "type": "choice",
                "instructions": "What next?",
                "criteria": {
                    "explorar": "Explore.",
                    "esperar": "Wait.",
                },
            }
        },
    )

    assert seen["questions"]["action"]["type"] == "choice"
    assert batch.answers["action"]["choice"] == "explorar"
    score, kind, calibrated = backend.choice_score(batch.answers["action"])
    assert score == 0.8
    assert kind == "confidence"
    assert calibrated is True


def test_laya_default_boolean_text_without_criteria(monkeypatch):
    class FakeRouter:
        def __init__(self, preload=False):
            pass

        def predict(self, state, questions, **kwargs):
            assert questions["x"]["criteria"]["A"].startswith("Yes")
            assert questions["x"]["criteria"]["B"].startswith("No")
            return {
                "answers": {
                    "x": {
                        "choice": "B",
                        "probabilities": {"A": 0.1, "B": 0.9},
                    }
                },
                "routing": {"model": "english"},
            }

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=FakeRouter))
    backend = LayaRecommendedBackend()
    batch = backend.predict(
        {"body": "state"},
        {"x": {"type": "noul", "instructions": "Is x true?"}},
    )
    assert batch.answers["x"]["noul"] == 0.1
