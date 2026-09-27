from agent_decision_eval.actions import (
    ACTION_DESCRIPTIONS,
    ALL_ACTIONS,
    READ_ONLY_ACTIONS,
    SENSITIVE_ACTIONS,
    Action,
)
from agent_decision_eval.tasks import TASKS


def test_all_ten_actions_present():
    assert len(ALL_ACTIONS) == 10
    assert set(ALL_ACTIONS) == {
        Action.ANSWER, Action.READ, Action.GREP, Action.FIND, Action.LS,
        Action.WRITE, Action.EDIT, Action.BASH, Action.WEB_SEARCH, Action.STOP,
    }


def test_every_action_has_a_description():
    for action in ALL_ACTIONS:
        assert action in ACTION_DESCRIPTIONS
        assert len(ACTION_DESCRIPTIONS[action]) > 0


def test_sensitive_and_read_only_are_disjoint_and_covered():
    assert SENSITIVE_ACTIONS.isdisjoint(READ_ONLY_ACTIONS)
    assert SENSITIVE_ACTIONS == {Action.WRITE, Action.EDIT, Action.BASH}


def test_task_set_has_at_least_50_tasks():
    assert len(TASKS) >= 50


def test_task_ids_are_unique():
    ids = [t.id for t in TASKS]
    assert len(ids) == len(set(ids))


def test_sensitive_actions_are_well_represented():
    # The success criteria hold write/edit/bash to a stricter accuracy bar,
    # so the benchmark needs enough of each to make that bar measurable.
    for action in SENSITIVE_ACTIONS:
        count = sum(1 for t in TASKS if t.expected_action == action)
        assert count >= 5, f"only {count} tasks for sensitive action {action}"


def test_every_action_has_at_least_one_task():
    covered = {t.expected_action for t in TASKS}
    assert covered == set(ALL_ACTIONS)


def test_stop_dataset_includes_an_unsafe_request_case():
    # At least one "stop" task must be an unsafe/out-of-scope request, so
    # dangerous-decision tracking has something adversarial to catch.
    assert any("delete" in t.state.lower() and "database" in t.state.lower() for t in TASKS if t.expected_action == Action.STOP)
