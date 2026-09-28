#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}"
export USE_TF=0

python experiments/run_experiment_v3c.py --variant rules
python experiments/run_experiment_v3c.py --variant julia_direct_choice
python experiments/run_experiment_v3c.py --variant laya_direct_choice
python experiments/report_round3c.py
