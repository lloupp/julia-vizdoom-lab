#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}"
export USE_TF=0

python experiments/run_experiment_v3b.py --variant rules
python experiments/run_experiment_v3b.py --variant julia_recommended
python experiments/run_experiment_v3b.py --variant laya_recommended
python experiments/report_round3b.py
