#!/usr/bin/env bash
# Runs all 6 round-2 variant configurations sequentially (rules, julia_raw,
# julia_filtered, julia_filtered_fallback x {0.60, 0.75, 0.90}), Fase A
# (seeds 1000-1019) + Fase B (seeds 5000-5029) each. Sequential, not
# parallel, on purpose: this machine has 4 cores and Julia-1 inference is
# CPU-bound, so running variants concurrently would just contend for the
# same cores and slow every one of them down.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH=.

COMMON="--seeds-a 1000-1019 --seeds-b 5000-5029 --episode-timeout 2400 --frame-skip 8 --out-dir logs_round2"

echo "=== rules ==="
python3 experiments/run_experiment_v2.py --variant rules $COMMON

echo "=== julia_raw ==="
python3 experiments/run_experiment_v2.py --variant julia_raw $COMMON

echo "=== julia_filtered ==="
python3 experiments/run_experiment_v2.py --variant julia_filtered $COMMON

echo "=== julia_filtered_fallback t60 ==="
python3 experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.60 $COMMON

echo "=== julia_filtered_fallback t75 ==="
python3 experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.75 $COMMON

echo "=== julia_filtered_fallback t90 ==="
python3 experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.90 $COMMON

echo "=== ALL ROUND 2 VARIANTS DONE ==="
