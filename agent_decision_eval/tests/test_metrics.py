from agent_decision_eval.metrics import (
    accuracy,
    accuracy_for,
    agreement_rate,
    dangerous_incorrect_count,
    indecision_rate,
    is_dangerous_incorrect,
    is_stable,
    latency_stats,
    percentile,
    resource_stats,
    sensitive_accuracy,
    summarize_mode,
)
from agent_decision_eval.actions import Action


def rec(expected, final, laya=None, julia=None, divergence=False, used_fallback=False, error=None,
        latency=10.0, rss_mb=100.0, cpu_percent=5.0):
    return {
        "expected_action": expected,
        "final_action": final,
        "laya_choice": laya,
        "julia_choice": julia,
        "divergence": divergence,
        "used_fallback": used_fallback,
        "error": error,
        "total_latency_ms": latency,
        "rss_mb": rss_mb,
        "cpu_percent": cpu_percent,
    }


def test_accuracy_basic():
    records = [rec("read", "read"), rec("write", "edit"), rec("ls", "ls")]
    assert accuracy(records) == 2 / 3


def test_accuracy_for_filters_by_expected_category():
    records = [
        rec("write", "write"),  # sensitive, correct
        rec("edit", "bash"),  # sensitive, wrong
        rec("read", "read"),  # not sensitive
    ]
    assert accuracy_for(records, frozenset({Action.WRITE, Action.EDIT, Action.BASH})) == 0.5


def test_sensitive_accuracy_uses_the_real_constant():
    records = [rec("write", "write"), rec("edit", "edit"), rec("bash", "read")]
    assert sensitive_accuracy(records) == 2 / 3


def test_dangerous_incorrect_requires_final_action_sensitive_and_wrong():
    dangerous = rec("stop", "bash")  # wrong AND sensitive -> dangerous
    wrong_but_safe = rec("stop", "answer")  # wrong but not sensitive
    correct_sensitive = rec("bash", "bash")  # sensitive but correct
    assert is_dangerous_incorrect(dangerous) is True
    assert is_dangerous_incorrect(wrong_but_safe) is False
    assert is_dangerous_incorrect(correct_sensitive) is False
    assert dangerous_incorrect_count([dangerous, wrong_but_safe, correct_sensitive]) == 1


def test_agreement_rate_only_over_parallel_style_records():
    records = [
        rec("read", "read", laya="read", julia="read"),
        rec("read", "read", laya="read", julia="grep"),
        rec("write", "write"),  # no laya/julia choices logged -> excluded
    ]
    assert agreement_rate(records) == 0.5


def test_agreement_rate_none_without_dual_model_records():
    assert agreement_rate([rec("read", "read")]) is None


def test_indecision_rate_per_mode_semantics():
    parallel_records = [
        rec("read", "read", divergence=False),
        rec("read", "read", divergence=True),
    ]
    fallback_records = [
        rec("read", "read", used_fallback=False),
        rec("read", "read", used_fallback=True),
        rec("read", "read", used_fallback=True),
    ]
    solo_records = [rec("read", "read")]

    assert indecision_rate("parallel", parallel_records) == 0.5
    assert indecision_rate("primary_fallback", fallback_records) == 2 / 3
    assert indecision_rate("laya_only", solo_records) == 0.0
    assert indecision_rate("julia_only", solo_records) == 0.0


def test_percentile_matches_known_values():
    values = list(range(1, 101))
    assert percentile(values, 95) == 95.05
    assert percentile([], 95) is None


def test_latency_stats():
    records = [rec("read", "read", latency=10.0), rec("read", "read", latency=30.0)]
    stats = latency_stats(records)
    assert stats["avg_latency_ms"] == 20.0
    assert stats["max_latency_ms"] == 30.0


def test_resource_stats_detects_no_growth():
    records = [rec("read", "read", rss_mb=100.0 + i * 0.01) for i in range(100)]
    stats = resource_stats(records)
    assert stats["possible_leak"] is False
    assert stats["max_rss_mb"] < 102.0


def test_resource_stats_flags_a_real_leak():
    records = [rec("read", "read", rss_mb=100.0 + i) for i in range(100)]  # +1MB every decision
    stats = resource_stats(records)
    assert stats["possible_leak"] is True
    assert stats["rss_growth_mb"] > 50.0


def test_is_stable_requires_500_decisions_no_errors_no_leak():
    good = [rec("read", "read") for _ in range(500)]
    assert is_stable(good, 500) is True

    too_few = [rec("read", "read") for _ in range(400)]
    assert is_stable(too_few, 500) is False

    with_error = [rec("read", "read") for _ in range(499)] + [rec("read", "read", error="boom")]
    assert is_stable(with_error, 500) is False

    leaking = [rec("read", "read", rss_mb=100.0 + i) for i in range(500)]
    assert is_stable(leaking, 500) is False


def test_summarize_mode_bundles_everything():
    records = [
        rec("write", "write", laya="write", julia="write"),
        rec("read", "grep", laya="read", julia="grep", divergence=True),
    ]
    summary = summarize_mode("parallel", records)
    assert summary["decisions"] == 2
    assert summary["accuracy"] == 0.5
    assert summary["indecision_rate"] == 0.5
    assert "p95_latency_ms" in summary
