"""Laya backend adapted to the model's documented recommended usage.

Round 3 intentionally forced laya-typed-decisions and used native noul for the
same hierarchy as Julia. The Laya documentation says two things that matter for
this benchmark:

1. typed-decisions is specialized to four specific workflows and should not be
   the silent default for an unrelated domain;
2. noul can become dominated by the literal false/true labels; when that happens
   the documented workaround is a two-option choice with neutral keys.

This backend therefore lets Router select the English general checkpoint and
transparently renders each incoming noul question as a neutral A/B choice. It
normalizes the result back into the noul shape expected by the shared hierarchy,
so the game policy itself stays unchanged.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping

from round3.backends import BackendBatch, DecisionBackend


class LayaRecommendedBackend(DecisionBackend):
    name = "laya"
    noul_is_calibrated = False

    def __init__(self, preload: bool = False) -> None:
        try:
            from laya import Router
        except ImportError as exc:
            raise RuntimeError(
                "Laya is not installed. Run pip install -U 'laya>=0.3.20'."
            ) from exc
        self._router = Router(preload=preload)

    @staticmethod
    def _render_questions(questions: dict) -> tuple[dict, set[str]]:
        rendered: Dict[str, dict] = {}
        converted_noul: set[str] = set()

        for key, question in questions.items():
            if question.get("type") != "noul":
                rendered[key] = dict(question)
                continue

            criteria = dict(question.get("criteria") or {})
            true_text = criteria.get("true") or "Yes, the proposition is true."
            false_text = criteria.get("false") or "No, the proposition is false."
            rendered[key] = {
                "type": "choice",
                "instructions": question["instructions"],
                "criteria": {
                    "A": true_text,
                    "B": false_text,
                },
            }
            converted_noul.add(key)

        return rendered, converted_noul

    @staticmethod
    def _normalize_answers(
        answers: Mapping[str, Mapping[str, Any]],
        converted_noul: set[str],
    ) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}

        for key, answer_in in answers.items():
            answer = dict(answer_in)
            if key not in converted_noul:
                normalized[key] = answer
                continue

            probabilities = {
                str(k): float(v)
                for k, v in dict(answer.get("probabilities") or {}).items()
            }
            p_true = float(probabilities.get("A", 0.0))
            p_false = float(probabilities.get("B", max(0.0, 1.0 - p_true)))
            normalized[key] = {
                "type": "noul",
                "noul": p_true,
                "probabilities": {
                    "false": p_false,
                    "true": p_true,
                },
                "source_type": "neutral_binary_choice",
                "source_choice": answer.get("choice"),
                "source_confidence": answer.get("confidence"),
            }

        return normalized

    def predict(self, state: dict, questions: dict) -> BackendBatch:
        rendered, converted_noul = self._render_questions(questions)

        started = time.perf_counter()
        # No explicit model override: for this English benchmark the recommended
        # Router selects the general English checkpoint instead of the
        # typed-decisions specialist.
        result = self._router.predict(state, rendered)
        latency_ms = (time.perf_counter() - started) * 1000.0

        routing = dict(result.get("routing") or {})
        answers = self._normalize_answers(result["answers"], converted_noul)
        return BackendBatch(
            answers=answers,
            latency_ms=latency_ms,
            metadata={
                "backend": self.name,
                "checkpoint": routing.get("model"),
                "routing": routing,
                "boolean_encoding": (
                    "neutral_two_option_choice" if converted_noul else "native_choice"
                ),
            },
        )

    def choice_score(self, answer: Mapping[str, Any]) -> tuple[float, str, bool]:
        if answer.get("confidence") is not None:
            return float(answer["confidence"]), "confidence", True
        choice = str(answer["choice"])
        probabilities = dict(answer.get("probabilities") or {})
        score = float(answer.get("answer_confidence", probabilities.get(choice, 0.0)))
        return score, "answer_confidence", False
