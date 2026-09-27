"""Paired comparison against the rules baseline, with a 95% confidence interval.

Pairing is by seed, not by position: variant and baseline ran the very same
seed, so their per-seed metric values are naturally paired observations
(not independent samples) -- the right basis for a paired-difference test
here, and safer than pairing by list index if an episode is ever missing
for one side.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional

# Two-tailed 95% critical values for Student's t distribution, indexed by
# degrees of freedom (n-1). Beyond this table, falls back to the normal
# approximation (z=1.96), which is already accurate to 3 decimal places
# by df=120.
_T_TABLE_95: Dict[int, float] = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    40: 2.021, 60: 2.000, 120: 1.980,
}


def t_critical_95(df: int) -> float:
    """Two-tailed 95% t critical value for ``df`` degrees of freedom."""
    if df < 1:
        return float("nan")
    if df in _T_TABLE_95:
        return _T_TABLE_95[df]
    if df > max(_T_TABLE_95):
        return 1.96  # normal approximation, accurate to 3 decimals by df=120
    below = [d for d in _T_TABLE_95 if d <= df]
    return _T_TABLE_95[max(below)]


@dataclass(frozen=True)
class PairedComparison:
    metric: str
    n_pairs: int
    mean_diff: Optional[float]  # variant - baseline, averaged over paired seeds
    ci95_low: Optional[float]
    ci95_high: Optional[float]
    significant: bool  # True iff the 95% CI excludes 0
    direction: str  # "higher_is_better" | "lower_is_better"
    worse: bool  # significant AND in the direction that hurts the variant


def paired_diff_ci95(
    baseline_by_seed: Dict[int, float], variant_by_seed: Dict[int, float]
) -> Dict[str, Optional[float]]:
    """Paired mean difference (variant - baseline) with a 95% CI, paired by seed."""
    shared_seeds = sorted(set(baseline_by_seed) & set(variant_by_seed))
    diffs = [variant_by_seed[s] - baseline_by_seed[s] for s in shared_seeds]
    n = len(diffs)

    if n == 0:
        return {"n_pairs": 0, "mean_diff": None, "ci95_low": None, "ci95_high": None}
    if n == 1:
        return {"n_pairs": 1, "mean_diff": diffs[0], "ci95_low": None, "ci95_high": None}

    mean_diff = sum(diffs) / n
    variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
    sd = math.sqrt(variance)
    se = sd / math.sqrt(n)
    margin = t_critical_95(n - 1) * se
    return {
        "n_pairs": n,
        "mean_diff": mean_diff,
        "ci95_low": mean_diff - margin,
        "ci95_high": mean_diff + margin,
    }


def compare_to_baseline(
    metric: str,
    baseline_by_seed: Dict[int, float],
    variant_by_seed: Dict[int, float],
    direction: str = "higher_is_better",
) -> PairedComparison:
    """95%-CI paired comparison of ``variant`` against ``baseline`` on ``metric``.

    ``direction`` says which side is "better" for this metric (e.g. survival
    is ``higher_is_better``, damage taken is ``lower_is_better``); ``worse``
    is True only when the CI excludes 0 *and* sits on the harmful side.
    """
    ci = paired_diff_ci95(baseline_by_seed, variant_by_seed)
    low, high = ci["ci95_low"], ci["ci95_high"]
    significant = low is not None and high is not None and (low > 0 or high < 0)
    worse = False
    if significant:
        worse = (high < 0) if direction == "higher_is_better" else (low > 0)
    return PairedComparison(
        metric=metric,
        n_pairs=ci["n_pairs"],
        mean_diff=ci["mean_diff"],
        ci95_low=low,
        ci95_high=high,
        significant=significant,
        direction=direction,
        worse=worse,
    )
