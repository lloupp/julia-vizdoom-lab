from experiments.stats import compare_to_baseline, paired_diff_ci95, t_critical_95


def test_t_critical_known_values():
    assert t_critical_95(1) == 12.706
    assert t_critical_95(19) == 2.093
    assert abs(t_critical_95(300) - 1.96) < 1e-9


def test_t_critical_uses_nearest_lower_df_between_table_entries():
    # No entry for df=35; must use df=30's value, not interpolate or round up.
    assert t_critical_95(35) == t_critical_95(30)


def test_paired_diff_identical_values_has_zero_mean_and_is_not_significant():
    baseline = {1000: 10.0, 1001: 20.0, 1002: 15.0}
    variant = dict(baseline)
    result = compare_to_baseline("survival", baseline, variant)
    assert result.mean_diff == 0.0
    assert result.significant is False
    assert result.worse is False


def test_paired_diff_detects_a_clear_improvement():
    baseline = {s: 10.0 for s in range(1000, 1020)}
    variant = {s: 15.0 for s in range(1000, 1020)}  # consistently +5, zero variance
    result = compare_to_baseline("survival", baseline, variant, direction="higher_is_better")
    assert result.mean_diff == 5.0
    assert result.significant is True
    assert result.worse is False  # improvement, not a regression


def test_paired_diff_detects_a_significant_regression():
    baseline = {s: 10.0 for s in range(1000, 1020)}
    variant = {s: 6.0 for s in range(1000, 1020)}  # consistently -4
    result = compare_to_baseline("survival", baseline, variant, direction="higher_is_better")
    assert result.significant is True
    assert result.worse is True


def test_lower_is_better_flips_which_side_counts_as_worse():
    baseline = {s: 100.0 for s in range(1000, 1020)}
    variant = {s: 150.0 for s in range(1000, 1020)}  # damage taken went UP
    result = compare_to_baseline("damage_taken", baseline, variant, direction="lower_is_better")
    assert result.significant is True
    assert result.worse is True  # more damage is worse when lower_is_better


def test_noisy_data_with_small_effect_is_not_significant():
    # Small, noisy differences shouldn't cross the 95% CI threshold.
    baseline = {1000: 10.0, 1001: 12.0, 1002: 8.0, 1003: 11.0, 1004: 9.0}
    variant = {1000: 10.5, 1001: 11.0, 1002: 9.0, 1003: 10.5, 1004: 8.5}
    result = compare_to_baseline("survival", baseline, variant)
    assert result.significant is False


def test_pairs_only_on_shared_seeds():
    baseline = {1000: 10.0, 1001: 20.0, 9999: 999.0}  # 9999 not in variant
    variant = {1000: 12.0, 1001: 22.0, 1234: 1.0}  # 1234 not in baseline
    ci = paired_diff_ci95(baseline, variant)
    assert ci["n_pairs"] == 2


def test_single_pair_has_no_ci_but_reports_the_difference():
    result = compare_to_baseline("survival", {1000: 10.0}, {1000: 13.0})
    assert result.n_pairs == 1
    assert result.mean_diff == 3.0
    assert result.ci95_low is None
    assert result.significant is False


def test_no_shared_seeds_reports_nothing():
    result = compare_to_baseline("survival", {1000: 10.0}, {2000: 10.0})
    assert result.n_pairs == 0
    assert result.mean_diff is None
    assert result.significant is False
