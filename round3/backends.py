"""Typed-decision backends used by the round-3 VizDoom benchmark."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class BackendBatch:
    answers: Mapping[str, Mapping[str, Any]]
    latency_ms: float
    metadata: Dict[str, Any]


class DecisionBackend:
    name = "backend"
    noul_is_calibrated = False

    def predict(self, state: dict, questions: dict) -> BackendBatch:
        raise NotImplementedError

    def choice_score(self, answer: Mapping[str, Any]) -> tuple[float, str, bool]:
        raise NotImplementedError


class JuliaBackend(DecisionBackend):
    """Julia-1 using its current named-question API with strict encoding."""

    name = "julia"
    noul_is_calibrated = False

    def __init__(
        self,
        model_dir: str = "models/Julia-1",
        device: str = "cpu",
        max_length: int = 8192,
        head_length: int = 512,
    ) -> None:
        try:
            from julia import load_model
        except ImportError as exc:
            raise RuntimeError(
                "Julia runtime is not installed. Run python scripts/setup_julia_model.py first."
            ) from exc
        self._engine = load_model(
            model_dir,
            device=device,
            strict_encoding=True,
            max_length=max_length,
            head_length=head_length,
        )

    def predict(self, state: dict, questions: dict) -> BackendBatch:
        started = time.perf_counter()
        result = self._engine.predict(state=state, questions=questions)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return BackendBatch(
            answers=result["answers"],
            latency_ms=latency_ms,
            metadata={"backend": self.name, "checkpoint": "SupersonicLabs/Julia-1"},
        )

    def choice_score(self, answer: Mapping[str, Any]) -> tuple[float, str, bool]:
        choice = str(answer["choice"])
        probabilities = dict(answer.get("probabilities") or {})
        score = float(answer.get("max_probability", probabilities.get(choice, 0.0)))
        return score, "raw_max_probability", False


class LayaBackend(DecisionBackend):
    """Laya through the recommended Router, pinned to typed-decisions."""

    name = "laya"
    noul_is_calibrated = True

    def __init__(
        self,
        model: str = "typed-decisions",
        preload: bool = False,
        max_len: int = 1024,
    ) -> None:
        try:
            from laya import Router
        except ImportError as exc:
            raise RuntimeError("Laya is not installed. Run pip install -U 'laya>=0.3.20'.") from exc
        self.model = model
        self.max_len = max_len
        self._router = Router(preload=preload)

    def predict(self, state: dict, questions: dict) -> BackendBatch:
        started = time.perf_counter()
        result = self._router.predict(
            state,
            questions,
            model=self.model,
            max_len=self.max_len,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        routing = dict(result.get("routing") or {})
        return BackendBatch(
            answers=result["answers"],
            latency_ms=latency_ms,
            metadata={
                "backend": self.name,
                "checkpoint": self.model,
                "routing": routing,
            },
        )

    def choice_score(self, answer: Mapping[str, Any]) -> tuple[float, str, bool]:
        if answer.get("confidence") is not None:
            return float(answer["confidence"]), "calibrated_confidence", True
        choice = str(answer["choice"])
        probabilities = dict(answer.get("probabilities") or {})
        score = float(answer.get("answer_confidence", probabilities.get(choice, 0.0)))
        return score, "answer_confidence", False
