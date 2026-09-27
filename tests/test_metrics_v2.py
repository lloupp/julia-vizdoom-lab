from experiments.metrics_v2 import (
    aggregate_variant_v2,
    agreement_rate,
    by_seed,
    compute_episode_metrics_v2,
    is_forced,
    is_real_model_call,
)


def _decision(
    action="explorar",
    offered=("explorar", "esperar"),
    available=("explorar", "esperar"),
    confidence=1.0,
    model_confidence=None,
    fallback_used=False,
    antiloop_override=False,
    overridden_from=None,
    error=None,
    latency_ms=0.0,
    rule_shadow_action=None,
):
    d = {
        "action": action,
        "offered_actions": list(offered),
        "available_actions": list(available),
        "confidence": confidence,
        "model_confidence": model_confidence,
        "fallback_used": fallback_used,
        "antiloop_override": antiloop_override,
        "overridden_from": overridden_from,
        "error": error,
        "latency_ms": latency_ms,
    }
    if rule_shadow_action is not None:
        d["rule_shadow_action"] = rule_shadow_action
    return d


def test_is_real_model_call_requires_model_confidence():
    assert is_real_model_call(_decision(model_confidence=0.8)) is True
    assert is_real_model_call(_decision(model_confidence=None)) is False


def test_is_forced_checks_offered_actions_length_not_confidence():
    forced = _decision(offered=("explorar",), model_confidence=None)
    assert is_forced(forced) is True

    # A plain rule-agent decision (no model_confidence either) is NOT forced:
    # it was simply never asked to choose among a single option.
    rule_decision = _decision(offered=("explorar", "esperar"), model_confidence=None)
    assert is_forced(rule_decision) is False

    real_call = _decision(offered=("explorar", "esperar"), model_confidence=0.9)
    assert is_forced(real_call) is False

    fallback = _decision(offered=("explorar", "esperar"), model_confidence=0.3, fallback_used=True)
    assert is_forced(fallback) is False


def test_agreement_rate_uses_shadow_action():
    decisions = [
        _decision(action="explorar", rule_shadow_action="explorar"),
        _decision(action="esperar", rule_shadow_action="explorar"),
    ]
    assert agreement_rate(decisions) == 0.5


def test_agreement_rate_none_without_any_shadow_data():
    decisions = [_decision(), _decision()]
    assert agreement_rate(decisions) is None


def test_forced_steps_excluded_from_latency_and_model_confidence_stats():
    decisions = [
        _decision(offered=("explorar",), model_confidence=None, latency_ms=0.0),  # forced
        _decision(model_confidence=0.8, latency_ms=40.0),
        _decision(model_confidence=0.6, latency_ms=60.0),
    ]
    metrics = compute_episode_metrics_v2(decisions, {"episode_id": 0, "seed": 1000, "died": True})
    assert metrics["real_model_calls"] == 2
    assert metrics["avg_latency_ms"] == 50.0  # only the two real calls
    assert metrics["avg_model_confidence"] == 0.7
    assert metrics["forced_count"] == 1


def test_wait_override_count_only_counts_overrides_from_wait():
    decisions = [
        _decision(antiloop_override=True, overridden_from="esperar"),
        _decision(antiloop_override=True, overridden_from="explorar"),
        _decision(antiloop_override=False, overridden_from=None),
    ]
    metrics = compute_episode_metrics_v2(decisions, {"episode_id": 0, "seed": 1000, "died": True})
    assert metrics["antiloop_override_count"] == 2
    assert metrics["wait_override_count"] == 1


def test_invalid_action_checked_against_offered_not_available():
    # atacar wasn't offered (filtered out) even though it was available.
    decisions = [_decision(action="atacar", offered=("explorar",), available=("atacar", "explorar"))]
    metrics = compute_episode_metrics_v2(decisions, {"episode_id": 0, "seed": 1000, "died": True})
    assert metrics["invalid_action_count"] == 1


def test_action_distribution_and_aggregate():
    episode_metrics = [
        compute_episode_metrics_v2(
            [_decision(action="explorar"), _decision(action="atacar")],
            {"episode_id": 0, "seed": 1000, "died": True, "survival_seconds": 10.0},
        ),
        compute_episode_metrics_v2(
            [_decision(action="explorar")],
            {"episode_id": 1, "seed": 1001, "died": False, "survival_seconds": 20.0},
        ),
    ]
    agg = aggregate_variant_v2(episode_metrics)
    assert agg["episodes"] == 2
    assert agg["action_distribution_total"] == {"explorar": 2, "atacar": 1}
    assert agg["survival_seconds"] == 15.0


def test_by_seed_maps_metric_to_seed():
    episode_metrics = [
        {"seed": 1000, "survival_seconds": 10.0},
        {"seed": 1001, "survival_seconds": 20.0},
        {"seed": 1002, "survival_seconds": None},
    ]
    result = by_seed(episode_metrics, "survival_seconds")
    assert result == {1000: 10.0, 1001: 20.0}
