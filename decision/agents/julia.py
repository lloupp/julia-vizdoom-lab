"""Agent backed by the real SupersonicLabs/Julia-1 decision model.

Julia-1 is a small (144.3M param) encoder-based *decision* model: given a
state description, a question and 2-20 labeled candidate answers, it returns
a probability distribution over the candidates. See
scripts/setup_julia_model.py for the one-time download/install step.
"""

from __future__ import annotations

import time
from typing import Dict, Sequence

from decision.actions import ACTION_DESCRIPTIONS, Action
from decision.agents.base import Decision, DecisionAgent
from decision.state import GameState

DEFAULT_MODEL_DIR = "models/Julia-1"


class JuliaUnavailableError(RuntimeError):
    """Raised when the 'julia' package or model weights are not installed."""


def describe_state(state: GameState) -> str:
    """Render the minimal state as plain text for the model's ``state`` input."""
    parts = [f"Health: {state.health:.0f}/100.", f"Ammo: {state.ammo}."]
    if state.enemies_visible > 0:
        distance = (
            "unknown" if state.enemy_distance is None else f"{state.enemy_distance:.0f} units"
        )
        parts.append(f"{state.enemies_visible} enemy(ies) visible at distance {distance}.")
    else:
        parts.append("No enemies visible.")
    parts.append("A medkit is visible." if state.medkit_visible else "No medkit visible.")
    parts.append("Ammo pickup is visible." if state.ammo_visible else "No ammo pickup visible.")
    return " ".join(parts)


class JuliaAgent(DecisionAgent):
    name = "julia"

    def __init__(
        self,
        model_dir: str = DEFAULT_MODEL_DIR,
        device: str = "cpu",
        max_length: int = 8192,
        head_length: int = 512,
    ) -> None:
        try:
            from julia import load_model
        except ImportError as exc:
            raise JuliaUnavailableError(
                "The 'julia' package is not installed. Run "
                "'python scripts/setup_julia_model.py' first."
            ) from exc

        try:
            self._engine = load_model(
                model_dir,
                device=device,
                strict_encoding=True,
                max_length=max_length,
                head_length=head_length,
            )
        except Exception as exc:
            raise JuliaUnavailableError(
                f"Failed to load Julia-1 from '{model_dir}'. Run "
                "'python scripts/setup_julia_model.py' first. "
                f"Original error: {type(exc).__name__}: {exc}"
            ) from exc

    def predict_raw(self, state: GameState, ordered_actions: Sequence[Action]) -> dict:
        """Calls the real model with candidates in exactly the given order.

        Python dicts preserve insertion order, so ``criteria`` presents the
        options to Julia-1 in ``ordered_actions`` order. Returns the raw
        ``answers["action"]`` dict (keys: ``choice``, ``probabilities``,
        ``max_probability``). Both ``decide()`` and the order-invariance test
        (``experiments/invariance_test.py``) go through this same method, so
        they exercise the identical code path -- the only thing that varies
        between them is the order of ``ordered_actions``.
        """
        criteria = {a.value: ACTION_DESCRIPTIONS[a] for a in ordered_actions}
        result = self._engine.predict(
            state=describe_state(state),
            questions={
                "action": {
                    "type": "choice",
                    "instructions": "Which action should the agent take right now?",
                    "criteria": criteria,
                }
            },
        )
        return result["answers"]["action"]

    def decide(self, state: GameState, available_actions: Sequence[Action]) -> Decision:
        start = time.perf_counter()
        try:
            answer = self.predict_raw(state, available_actions)
            latency_ms = (time.perf_counter() - start) * 1000
            choice_id = answer["choice"]
            probabilities: Dict[str, float] = {
                str(k): float(v) for k, v in dict(answer["probabilities"]).items()
            }
            confidence = float(answer.get("max_probability", probabilities.get(choice_id, 0.0)))
            action = Action(choice_id)
            return Decision(
                action=action,
                confidence=confidence,
                source=self.name,
                model_confidence=confidence,
                probabilities=probabilities,
                latency_ms=latency_ms,
            )
        except Exception as exc:  # model failure must never crash the episode
            latency_ms = (time.perf_counter() - start) * 1000
            safe_action = Action.WAIT if Action.WAIT in available_actions else available_actions[0]
            return Decision(
                action=safe_action,
                confidence=0.0,
                source=self.name,
                model_confidence=0.0,
                latency_ms=latency_ms,
                error=f"{type(exc).__name__}: {exc}",
            )
