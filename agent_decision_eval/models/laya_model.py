"""Wraps the real convaiinnovations/laya-multilingual model for tool-routing."""

from __future__ import annotations

import time
from typing import Dict, Sequence

from agent_decision_eval.actions import ACTION_DESCRIPTIONS, Action
from agent_decision_eval.models.base import DecisionModel, ModelDecision
from agent_decision_eval.tasks import Task

DEFAULT_MODEL_DIR = "models/laya-multilingual"

# Returned when the model call itself fails: the decision layer is broken,
# so the safest universal default is to halt rather than risk any action.
SAFE_DEFAULT_ON_ERROR = Action.STOP

_INSTRUCTIONS = "Which action should the coding agent take next, given the state below?"


class LayaModel(DecisionModel):
    name = "laya"

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR, device: str = "cpu") -> None:
        try:
            import laya
        except ImportError as exc:
            raise RuntimeError("The 'laya' package is not installed. Run 'pip install laya' first.") from exc

        self._agent = laya.load(model_dir, device=device)

    def predict(self, task: Task, options: Sequence[Action]) -> ModelDecision:
        criteria = {a.value: ACTION_DESCRIPTIONS[a] for a in options}
        start = time.perf_counter()
        try:
            result = self._agent.predict(
                {"body": task.state},
                {
                    "action": {
                        "type": "choice",
                        "instructions": _INSTRUCTIONS,
                        "criteria": criteria,
                    }
                },
            )
            latency_ms = (time.perf_counter() - start) * 1000
            answer = result["answers"]["action"]
            choice_id = answer["choice"]
            probabilities: Dict[str, float] = {
                str(k): float(v) for k, v in dict(answer["probabilities"]).items()
            }
            # Laya reports two distinct numbers: "answer_confidence" (the raw
            # top softmax probability, equivalent to Julia's max_probability)
            # and "confidence" (its own separately-computed estimate). Never
            # conflate the two.
            max_probability = float(answer.get("answer_confidence", probabilities.get(choice_id, 0.0)))
            model_confidence = answer.get("confidence")
            return ModelDecision(
                choice=Action(choice_id),
                probabilities=probabilities,
                max_probability=max_probability,
                model_confidence=float(model_confidence) if model_confidence is not None else None,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # a broken model call must never crash the harness
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelDecision(
                choice=SAFE_DEFAULT_ON_ERROR,
                latency_ms=latency_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
