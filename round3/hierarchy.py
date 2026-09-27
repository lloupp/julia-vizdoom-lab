"""Hierarchical noul -> small-choice policy shared by Julia and Laya."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence

from decision.actions import Action
from decision.state import GameState
from round3.backends import BackendBatch, DecisionBackend
from round3.prompts import BOOLEAN_QUESTIONS, build_model_state, choice_criteria, ordered_actions


@dataclass(frozen=True)
class HierarchyResult:
    action: Action
    score: float
    score_kind: str
    score_is_calibrated: bool
    probabilities: Dict[str, float] = field(default_factory=dict)
    boolean_probabilities: Dict[str, float] = field(default_factory=dict)
    stage: str = ""
    latency_ms: float = 0.0
    model_calls: int = 0
    backend_metadata: List[Dict[str, Any]] = field(default_factory=list)


def _noul_probability(answer: Mapping[str, Any]) -> float:
    if answer.get("noul") is not None:
        return float(answer["noul"])
    probabilities = dict(answer.get("probabilities") or {})
    return float(probabilities.get("true", 0.0))


def _answer_booleans(batch: BackendBatch) -> Dict[str, float]:
    return {
        key: _noul_probability(batch.answers[key])
        for key in BOOLEAN_QUESTIONS
    }


def _choice(
    backend: DecisionBackend,
    model_state: dict,
    candidates: Sequence[Action],
    *,
    stage: str,
    instructions: str,
    prior_booleans: Dict[str, float],
    prior_latency_ms: float,
    prior_metadata: List[Dict[str, Any]],
    prior_calls: int,
) -> HierarchyResult:
    ordered = ordered_actions(candidates)
    if len(ordered) == 1:
        return HierarchyResult(
            action=ordered[0],
            score=1.0,
            score_kind="forced_single_valid_action",
            score_is_calibrated=False,
            boolean_probabilities=prior_booleans,
            stage=stage + ":forced",
            latency_ms=prior_latency_ms,
            model_calls=prior_calls,
            backend_metadata=prior_metadata,
        )

    batch = backend.predict(
        model_state,
        {
            "action": {
                "type": "choice",
                "instructions": instructions,
                "criteria": choice_criteria(ordered),
            }
        },
    )
    answer = batch.answers["action"]
    choice_id = str(answer["choice"])
    valid_ids = {a.value for a in ordered}
    if choice_id not in valid_ids:
        raise ValueError(f"Model returned unavailable action {choice_id!r}; valid={sorted(valid_ids)}")

    score, score_kind, calibrated = backend.choice_score(answer)
    probabilities = {
        str(k): float(v) for k, v in dict(answer.get("probabilities") or {}).items()
    }
    return HierarchyResult(
        action=Action(choice_id),
        score=score,
        score_kind=score_kind,
        score_is_calibrated=calibrated,
        probabilities=probabilities,
        boolean_probabilities=prior_booleans,
        stage=stage,
        latency_ms=prior_latency_ms + batch.latency_ms,
        model_calls=prior_calls + 1,
        backend_metadata=prior_metadata + [batch.metadata],
    )


def decide_hierarchically(
    backend: DecisionBackend,
    state: GameState,
    available_actions: Sequence[Action],
) -> HierarchyResult:
    """Use one batched Boolean pass, then at most one small choice pass."""
    available = ordered_actions(available_actions)
    if not available:
        raise ValueError("No available actions")
    if len(available) == 1:
        return HierarchyResult(
            action=available[0],
            score=1.0,
            score_kind="forced_single_valid_action",
            score_is_calibrated=False,
            stage="single_valid_action",
            model_calls=0,
        )

    model_state = build_model_state(state, available)
    first = backend.predict(model_state, BOOLEAN_QUESTIONS)
    booleans = _answer_booleans(first)
    latency = first.latency_ms
    metadata = [first.metadata]
    calls = 1

    if booleans["survival_priority"] >= 0.5:
        survival = [
            action for action in (Action.FLEE, Action.SEEK_HEALTH)
            if action in available
        ]
        if survival:
            return _choice(
                backend,
                model_state,
                survival,
                stage="survival",
                instructions=(
                    "Immediate survival is the priority. Which available survival "
                    "action should the agent take now?"
                ),
                prior_booleans=booleans,
                prior_latency_ms=latency,
                prior_metadata=metadata,
                prior_calls=calls,
            )

    if booleans["engage_enemy"] >= 0.5 and Action.ATTACK in available:
        return HierarchyResult(
            action=Action.ATTACK,
            score=booleans["engage_enemy"],
            score_kind="noul_p_true",
            score_is_calibrated=backend.noul_is_calibrated,
            boolean_probabilities=booleans,
            stage="engage_enemy",
            latency_ms=latency,
            model_calls=calls,
            backend_metadata=metadata,
        )

    resource_candidates: List[Action] = []
    if booleans["seek_health"] >= 0.5 and Action.SEEK_HEALTH in available:
        resource_candidates.append(Action.SEEK_HEALTH)
    if booleans["seek_ammo"] >= 0.5 and Action.SEEK_AMMO in available:
        resource_candidates.append(Action.SEEK_AMMO)
    if resource_candidates:
        return _choice(
            backend,
            model_state,
            resource_candidates,
            stage="resource",
            instructions=(
                "The agent should pursue a visible resource. Which available "
                "resource objective should take priority now?"
            ),
            prior_booleans=booleans,
            prior_latency_ms=latency,
            prior_metadata=metadata,
            prior_calls=calls,
        )

    return _choice(
        backend,
        model_state,
        available,
        stage="general",
        instructions=(
            "Choose the best currently available action for the stated objective "
            "using only the supplied game state. Do not invent missing facts."
        ),
        prior_booleans=booleans,
        prior_latency_ms=latency,
        prior_metadata=metadata,
        prior_calls=calls,
    )
