import json

from decision.actions import ALL_ACTIONS, Action
from decision.agents.base import Decision
from decision.logging import DecisionLogger
from decision.state import GameState

STATE = GameState(health=100.0, ammo=50, enemies_visible=0, enemy_distance=None, medkit_visible=False, ammo_visible=False)


def test_logs_one_json_line_per_decision(tmp_path):
    path = tmp_path / "decisions.jsonl"
    decision = Decision(action=Action.EXPLORE, confidence=1.0, source="rules")

    with DecisionLogger(path) as logger:
        logger.log(
            agent_variant="rules",
            episode_id=0,
            step=0,
            state=STATE,
            available_actions=ALL_ACTIONS,
            decision=decision,
        )
        logger.log(
            agent_variant="rules",
            episode_id=0,
            step=1,
            state=STATE,
            available_actions=ALL_ACTIONS,
            decision=decision,
        )

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["action"] == "explorar"
    assert record["agent_variant"] == "rules"
    assert record["step"] == 0
    assert record["available_actions"] == [a.value for a in ALL_ACTIONS]
    assert record["confidence"] == 1.0
    assert record["fallback_used"] is False
    assert record["error"] is None


def test_appends_across_logger_instances(tmp_path):
    path = tmp_path / "decisions.jsonl"
    decision = Decision(action=Action.WAIT, confidence=1.0, source="rules")

    with DecisionLogger(path) as logger:
        logger.log(agent_variant="rules", episode_id=0, step=0, state=STATE, available_actions=ALL_ACTIONS, decision=decision)
    with DecisionLogger(path) as logger:
        logger.log(agent_variant="rules", episode_id=1, step=0, state=STATE, available_actions=ALL_ACTIONS, decision=decision)

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
