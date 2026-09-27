#!/usr/bin/env python3
"""Runs all 4 decision modes over the same 56-task set, each repeated to at
least --min-decisions (default 500) consecutive decisions, logging every
decision plus resource usage (RSS, CPU%) for the leak/stability check.

Both models are loaded exactly once and shared across every mode that
needs them (Laya's model load alone takes ~90s; reloading it per mode would
waste minutes for no reason).

Mode 3 (parallel) needs modes 1 and 2's own accuracy to break non-sensitive
disagreements, so the run order below is not arbitrary: 1, 2, then 3, 4.

Usage:
    python agent_decision_eval/run_eval.py --min-decisions 500
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path
from typing import List

import psutil

from agent_decision_eval.actions import READ_ONLY_ACTIONS, options_for_task
from agent_decision_eval.metrics import accuracy, accuracy_for
from agent_decision_eval.models.julia_model import JuliaModel
from agent_decision_eval.models.laya_model import LayaModel
from agent_decision_eval.modes import (
    CategoryAccuracy,
    JuliaOnlyMode,
    LayaOnlyMode,
    ParallelMode,
    PrimaryFallbackMode,
)
from agent_decision_eval.tasks import TASKS

MB = 1024 * 1024


def run_mode(mode, mode_name: str, out_path: Path, min_decisions: int) -> List[dict]:
    process = psutil.Process()
    process.cpu_percent(interval=None)  # prime the internal counter
    gc.collect()

    records: List[dict] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        step = 0
        cycle = 0
        while step < min_decisions:
            cycle += 1
            for task in TASKS:
                decision = mode.decide(task, options_for_task(task.id))
                record = {
                    "mode": mode_name,
                    "cycle": cycle,
                    "step": step,
                    "task_id": task.id,
                    "expected_action": task.expected_action.value,
                    "final_action": decision.final_action.value,
                    "source": decision.source,
                    "used_fallback": decision.used_fallback,
                    "divergence": decision.divergence,
                    "blocked_sensitive": decision.blocked_sensitive,
                    "total_latency_ms": decision.total_latency_ms,
                    "error": decision.error,
                    "laya_choice": decision.laya.choice.value if decision.laya else None,
                    "laya_max_probability": decision.laya.max_probability if decision.laya else None,
                    "laya_model_confidence": decision.laya.model_confidence if decision.laya else None,
                    "laya_probabilities": decision.laya.probabilities if decision.laya else None,
                    "julia_choice": decision.julia.choice.value if decision.julia else None,
                    "julia_max_probability": decision.julia.max_probability if decision.julia else None,
                    "julia_probabilities": decision.julia.probabilities if decision.julia else None,
                    "rss_mb": process.memory_info().rss / MB,
                    "cpu_percent": process.cpu_percent(interval=None),
                }
                f.write(json.dumps(record) + "\n")
                records.append(record)
                step += 1
                if step >= min_decisions:
                    break
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-decisions", type=int, default=500)
    parser.add_argument("--confidence-threshold", type=float, default=0.75)
    parser.add_argument("--laya-model-dir", type=str, default="models/laya-multilingual")
    parser.add_argument("--julia-model-dir", type=str, default="models/Julia-1")
    parser.add_argument("--out-dir", type=str, default="agent_decision_eval/logs")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Laya-multilingual (one-time, ~90s on CPU)...")
    t0 = time.time()
    laya = LayaModel(model_dir=args.laya_model_dir)
    print(f"  loaded in {time.time() - t0:.1f}s")

    print("Loading Julia-1...")
    t0 = time.time()
    julia = JuliaModel(model_dir=args.julia_model_dir)
    print(f"  loaded in {time.time() - t0:.1f}s")

    run_meta = {
        "started_at": time.time(),
        "min_decisions": args.min_decisions,
        "confidence_threshold": args.confidence_threshold,
        "task_count": len(TASKS),
    }
    (out_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

    print(f"\n=== mode 1: laya_only ({args.min_decisions}+ decisions) ===")
    t0 = time.time()
    laya_only_records = run_mode(LayaOnlyMode(laya), "laya_only", out_dir / "laya_only.jsonl", args.min_decisions)
    print(f"  done in {time.time() - t0:.1f}s, accuracy={accuracy(laya_only_records):.3f}")

    print(f"\n=== mode 2: julia_only ({args.min_decisions}+ decisions) ===")
    t0 = time.time()
    julia_only_records = run_mode(JuliaOnlyMode(julia), "julia_only", out_dir / "julia_only.jsonl", args.min_decisions)
    print(f"  done in {time.time() - t0:.1f}s, accuracy={accuracy(julia_only_records):.3f}")

    history = CategoryAccuracy(
        read_only_accuracy={
            "laya": accuracy_for(laya_only_records, READ_ONLY_ACTIONS),
            "julia": accuracy_for(julia_only_records, READ_ONLY_ACTIONS),
        },
        overall_accuracy={
            "laya": accuracy(laya_only_records),
            "julia": accuracy(julia_only_records),
        },
    )
    (out_dir / "category_accuracy_history.json").write_text(
        json.dumps(
            {"read_only_accuracy": history.read_only_accuracy, "overall_accuracy": history.overall_accuracy},
            indent=2,
        )
    )
    print(f"  history for mode 3: {history}")

    print(f"\n=== mode 3: parallel ({args.min_decisions}+ decisions) ===")
    t0 = time.time()
    parallel_records = run_mode(
        ParallelMode(laya, julia, history), "parallel", out_dir / "parallel.jsonl", args.min_decisions
    )
    print(f"  done in {time.time() - t0:.1f}s, accuracy={accuracy(parallel_records):.3f}")

    print(f"\n=== mode 4: primary_fallback (threshold={args.confidence_threshold}) ===")
    t0 = time.time()
    fallback_records = run_mode(
        PrimaryFallbackMode(laya, julia, args.confidence_threshold),
        "primary_fallback",
        out_dir / "primary_fallback.jsonl",
        args.min_decisions,
    )
    print(f"  done in {time.time() - t0:.1f}s, accuracy={accuracy(fallback_records):.3f}")

    print(f"\nDone. Logs written under {out_dir}/")


if __name__ == "__main__":
    main()
