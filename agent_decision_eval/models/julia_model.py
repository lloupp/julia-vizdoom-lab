"""Wraps the real SupersonicLabs/Julia-1 model for tool-routing decisions."""

from __future__ import annotations

import time
from typing import Dict, Sequence

from agent_decision_eval.actions import ACTION_DESCRIPTIONS, Action
from agent_decision_eval.models.base import DecisionModel, ModelDecision
from agent_decision_eval.tasks import Task

DEFAULT_MODEL_DIR = "models/Julia-1"

# Returned when the model call itself fails: the decision layer is broken,
# so the safest universal default is to halt rather than risk any action.
SAFE_DEFAULT_ON_ERROR = Action.STOP

_INSTRUCTIONS = "Which action should the coding agent take next, given the state below?"


class JuliaModel(DecisionModel):
    name = "julia"

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR, device: str = "cpu") -> None:
        try:
            from julia import load_model
        except ImportError as exc:
            raise RuntimeError(
                "The 'julia' package is not installed. Run "
                "'python scripts/setup_julia_model.py' first."
            ) from exc

        self._engine = load_model(
            model_dir, device=device, strict_encoding=True, max_length=8192, head_length=512
        )

    def predict(self, task: Task, options: Sequence[Action]) -> ModelDecision:
        criteria = {a.value: ACTION_DESCRIPTIONS[a] for a in options}
        start = time.perf_counter()
        try:
            result = self._engine.predict(
                state={"body": task.state},
                questions={
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
            max_probability = float(answer.get("max_probability", probabilities.get(choice_id, 0.0)))
            return ModelDecision(
                choice=Action(choice_id),
                probabilities=probabilities,
                max_probability=max_probability,
                model_confidence=None,  # Julia-1 doesn't expose one separate from max_probability
                latency_ms=latency_ms,
            )
        except Exception as exc:  # a broken model call must never crash the harness
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelDecision(
                choice=SAFE_DEFAULT_ON_ERROR,
                latency_ms=latency_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
