from experiments.metrics import aggregate_variant, compute_episode_metrics, percentile


def test_percentile_p50_and_p95_on_simple_range():
    values = list(range(1, 101))  # 1..100
    assert percentile(values, 50) == 50.5
    assert percentile(values, 95) == 95.05


def test_percentile_empty_is_none():
    assert percentile([], 95) is None


def test_percentile_single_value():
    assert percentile([42.0], 50) == 42.0


def _decision(action="explorar", available=("explorar", "esperar"), confidence=1.0,
              model_confidence=None, fallback_used=False, antiloop_override=False,
              error=None, latency_ms=0.0):
    return {
        "action": action,
        "available_actions": list(available),
        "confidence": confidence,
        "model_confidence": model_confidence,
        "fallback_used": fallback_used,
        "antiloop_override": antiloop_override,
        "error": error,
        "latency_ms": latency_ms,
    }


def test_compute_episode_metrics_counts_fallbacks_and_errors():
    decisions = [
        _decision(fallback_used=False, model_confidence=0.9, latency_ms=10.0),
        _decision(fallback_used=True, model_confidence=0.2, latency_ms=20.0, error="boom"),
    ]
    summary = {"episode_id": 0, "kills": 1, "survival_tics": 100}

    metrics = compute_episode_metrics(decisions, summary)

    assert metrics["decisions"] == 2
    assert metrics["fallback_count"] == 1
    assert metrics["fallback_rate"] == 0.5
    assert metrics["error_count"] == 1
    assert metrics["avg_confidence"] == 1.0
    assert metrics["avg_model_confidence"] == (0.9 + 0.2) / 2
    assert metrics["kills"] == 1  # carried over from the summary row


def test_compute_episode_metrics_counts_antiloop_overrides_separately_from_fallbacks():
    decisions = [
        _decision(fallback_used=True, antiloop_override=False),
        _decision(fallback_used=False, antiloop_override=True),
    ]
    metrics = compute_episode_metrics(decisions, {"episode_id": 0})
    assert metrics["fallback_count"] == 1
    assert metrics["antiloop_override_count"] == 1


def test_compute_episode_metrics_flags_invalid_actions():
    decisions = [_decision(action="atacar", available=("explorar", "esperar"))]
    metrics = compute_episode_metrics(decisions, {"episode_id": 0})
    assert metrics["invalid_action_count"] == 1


def test_aggregate_variant_averages_across_episodes():
    episode_metrics = [
        {"survival_tics": 100, "survival_seconds": 2.9, "kills": 1, "damage_taken": 10, "ammo_consumed": 5,
         "decisions": 10, "avg_confidence": 1.0, "avg_model_confidence": None, "fallback_count": 0,
         "fallback_rate": 0.0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "error_count": 0,
         "invalid_action_count": 0, "died": True},
        {"survival_tics": 200, "survival_seconds": 5.7, "kills": 3, "damage_taken": 20, "ammo_consumed": 15,
         "decisions": 20, "avg_confidence": 1.0, "avg_model_confidence": None, "fallback_count": 0,
         "fallback_rate": 0.0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0, "error_count": 0,
         "invalid_action_count": 0, "died": False},
    ]
    agg = aggregate_variant(episode_metrics)
    assert agg["episodes"] == 2
    assert agg["kills"] == 2.0
    assert agg["death_rate"] == 0.5
    assert agg["avg_model_confidence"] is None


def test_aggregate_variant_empty_input():
    assert aggregate_variant([]) == {}
