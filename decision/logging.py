"""JSONL logger for every decision made during an episode."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Sequence, TextIO

from decision.actions import Action
from decision.agents.base import Decision
from decision.state import GameState


class DecisionLogger:
    """Appends one JSON object per decision to a file, flushing every write.

    Flushing immediately trades a little throughput for the guarantee that
    logs are real even if a run crashes mid-episode -- required since these
    logs are the raw evidence behind the final report.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO = self.path.open("a", encoding="utf-8")

    def log(
        self,
        *,
        agent_variant: str,
        episode_id: int,
        step: int,
        state: GameState,
        available_actions: Sequence[Action],
        decision: Decision,
        extra: Optional[dict] = None,
    ) -> None:
        record = {
            "timestamp": time.time(),
            "agent_variant": agent_variant,
            "episode_id": episode_id,
            "step": step,
            "state": state.as_dict(),
            "available_actions": [a.value for a in available_actions],
            "action": decision.action.value,
            "confidence": decision.confidence,
            "model_confidence": decision.model_confidence,
            "source": decision.source,
            "probabilities": decision.probabilities,
            "latency_ms": decision.latency_ms,
            "fallback_used": decision.fallback_used,
            "antiloop_override": decision.antiloop_override,
            "error": decision.error,
        }
        if extra:
            record.update(extra)
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "DecisionLogger":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
