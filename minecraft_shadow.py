"""Minecraft-only Julia-1 shadow evaluator.

This module deliberately does not reuse the VizDoom Action enum. It accepts the
same action ids used by minecraft-mbot/conversa-llm and never executes them.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Mapping, Sequence

MINECRAFT_ACTIONS = (
    "gather", "craft", "smelt", "eat", "move", "deposit",
    "withdraw", "build", "fight", "wait", "stop",
)

ACTION_DESCRIPTIONS = {
    "gather": "Collect a required world resource.",
    "craft": "Craft the required item from available ingredients.",
    "smelt": "Use a furnace to process the required material.",
    "eat": "Eat available food when hunger makes it appropriate.",
    "move": "Move toward a safe or required destination.",
    "deposit": "Put inventory items into storage.",
    "withdraw": "Take required items from storage.",
    "build": "Place blocks to complete the current construction objective.",
    "fight": "Defend against or attack a hostile mob when appropriate.",
    "wait": "Do nothing while waiting for a safe next step.",
    "stop": "Stop the current objective after cancellation.",
}


@dataclass(frozen=True)
class ShadowDecision:
    action: str
    confidence: float
    probabilities: dict[str, float]
    latency_ms: float
    valid: bool
    error: str | None = None


class MinecraftJuliaShadow:
    def __init__(self, engine) -> None:
        self._engine = engine

    def decide(self, state: Mapping, available_actions: Sequence[str] = MINECRAFT_ACTIONS) -> ShadowDecision:
        offered = tuple(a for a in available_actions if a in ACTION_DESCRIPTIONS)
        if not offered:
            return ShadowDecision("wait", 0.0, {}, 0.0, False, "no_valid_actions")
        criteria = {action: ACTION_DESCRIPTIONS[action] for action in offered}
        started = time.perf_counter()
        try:
            result = self._engine.predict(
                state=_describe_state(state),
                questions={"action": {
                    "type": "choice",
                    "instructions": "Which safe Minecraft action should the worker take next?",
                    "criteria": criteria,
                }},
            )
            answer = result["answers"]["action"]
            probabilities = {str(k): float(v) for k, v in dict(answer["probabilities"]).items()}
            action = str(answer["choice"])
            confidence = float(answer.get("max_probability", probabilities.get(action, 0.0)))
            return ShadowDecision(
                action, confidence, probabilities,
                (time.perf_counter() - started) * 1000,
                action in offered,
                None if action in offered else "invalid_action",
            )
        except Exception as exc:
            return ShadowDecision(
                "wait", 0.0, {}, (time.perf_counter() - started) * 1000,
                False, f"{type(exc).__name__}: {exc}",
            )


def _describe_state(state: Mapping) -> str:
    inventory = state.get("inventory") or {}
    inventory_text = ", ".join(f"{k}={inventory[k]}" for k in sorted(inventory)) or "empty"
    return (
        f"Health: {state.get('health', 0)}. Hunger: {state.get('food', 0)}. "
        f"Objective: {state.get('objective') or 'none'}. "
        f"Inventory: {inventory_text}."
    )
