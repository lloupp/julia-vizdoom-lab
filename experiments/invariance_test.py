#!/usr/bin/env python3
"""Order-invariance test: does shuffling the option order change Julia-1's pick?

Julia-1's ``max_probability`` is a raw softmax score, not a calibrated
confidence -- the only way to know how much to trust a single decision is to
empirically probe it, which is what this script does: for real states drawn
from an actual round-2 run, it calls the SAME model on the SAME state with
the SAME candidate actions in different orders, and records whether the
``choice`` changes. If it does, that decision was decided by presentation
order at least as much as by content.

Permutations are generated deterministically (rotations of the original
order and of its reverse, deduplicated) -- no RNG involved, so this script's
output is exactly reproducible from the same input logs.

Usage:
    python experiments/invariance_test.py --logs-dir logs_round2
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from decision.actions import Action
from decision.agents.julia import JuliaAgent
from decision.state import GameState
from experiments.metrics import load_jsonl, mean

StateKey = Tuple[tuple, Tuple[str, ...]]


def generate_permutations(actions: List[str], k: int) -> List[List[str]]:
    """Up to ``k`` distinct orderings: rotations of ``actions`` and of its
    reverse. For 2 actions this is exhaustive (both possible orders)."""
    n = len(actions)
    seen = set()
    perms: List[List[str]] = []

    def add(seq: List[str]) -> None:
        key = tuple(seq)
        if key not in seen:
            seen.add(key)
            perms.append(seq)

    for i in range(n):
        add(actions[i:] + actions[:i])
    reversed_actions = list(reversed(actions))
    for i in range(n):
        if len(perms) >= k:
            break
        add(reversed_actions[i:] + reversed_actions[:i])
    return perms[:k]


def state_from_dict(d: dict) -> GameState:
    return GameState(
        health=d["health"],
        ammo=d["ammo"],
        enemies_visible=d["enemies_visible"],
        enemy_distance=d["enemy_distance"],
        medkit_visible=d["medkit_visible"],
        ammo_visible=d["ammo_visible"],
    )


def sample_unique_states(decisions: List[dict], cap: int) -> List[dict]:
    """Deterministic, evenly-spaced sample of unique (state, offered) pairs.

    Skips steps with fewer than 2 offered actions (nothing to permute) and
    steps where Julia-1 wasn't actually called (model_confidence is None --
    e.g. ``ActionFilterGuard`` forced a single action, or the source is the
    "rules" baseline, which never has an ``offered_actions`` >= 2 either way
    unless it happens to coincide -- excluded regardless since it's not a
    Julia decision).
    """
    unique: Dict[StateKey, dict] = {}
    for d in decisions:
        offered = d.get("offered_actions") or d.get("available_actions") or []
        if len(offered) < 2 or d.get("model_confidence") is None:
            continue
        key: StateKey = (tuple(sorted(d["state"].items())), tuple(offered))
        unique.setdefault(key, d)

    ordered = list(unique.values())
    if len(ordered) <= cap:
        return ordered
    stride = len(ordered) / cap
    return [ordered[int(i * stride)] for i in range(cap)]


def run_invariance_test(
    agent: JuliaAgent, sampled: List[dict], permutations_per_state: int
) -> List[dict]:
    results = []
    for d in sampled:
        state = state_from_dict(d["state"])
        offered = d["offered_actions"]
        perms = generate_permutations(offered, permutations_per_state)

        choices = []
        for perm in perms:
            ordered_actions = [Action(v) for v in perm]
            answer = agent.predict_raw(state, ordered_actions)
            choices.append({"order": perm, "choice": answer["choice"], "max_probability": answer["max_probability"]})

        distinct_choices = {c["choice"] for c in choices}
        counts = Counter(c["choice"] for c in choices)
        majority_fraction = counts.most_common(1)[0][1] / len(choices)

        results.append(
            {
                "state": d["state"],
                "offered_actions": offered,
                "source_variant": d["agent_variant"],
                "n_permutations": len(perms),
                "distinct_choices": sorted(distinct_choices),
                "unstable": len(distinct_choices) > 1,
                "majority_fraction": majority_fraction,
                "choices": choices,
            }
        )
    return results


def summarize(results: List[dict]) -> dict:
    by_source: Dict[str, List[dict]] = {}
    for r in results:
        by_source.setdefault(r["source_variant"], []).append(r)

    summary = {}
    for source, rows in by_source.items():
        summary[source] = {
            "states_tested": len(rows),
            "instability_rate": mean([1.0 if r["unstable"] else 0.0 for r in rows]),
            "avg_majority_fraction": mean([r["majority_fraction"] for r in rows]),
            "avg_distinct_choices": mean([len(r["distinct_choices"]) for r in rows]),
        }
    all_rows = results
    summary["overall"] = {
        "states_tested": len(all_rows),
        "instability_rate": mean([1.0 if r["unstable"] else 0.0 for r in all_rows]),
        "avg_majority_fraction": mean([r["majority_fraction"] for r in all_rows]),
        "avg_distinct_choices": mean([len(r["distinct_choices"]) for r in all_rows]),
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=str, default="logs_round2")
    parser.add_argument("--model-dir", type=str, default="models/Julia-1")
    parser.add_argument(
        "--sources",
        type=str,
        default="julia_raw,julia_filtered",
        help="Comma-separated variant directory names to sample states from.",
    )
    parser.add_argument("--cap-per-source", type=int, default=100)
    parser.add_argument("--permutations-per-state", type=int, default=6)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    sampled: List[dict] = []
    for source in sources:
        decisions = load_jsonl(logs_dir / source / "decisions.jsonl")
        sampled.extend(sample_unique_states(decisions, args.cap_per_source))

    print(f"Sampled {len(sampled)} unique (state, offered_actions) pairs from {sources}")

    agent = JuliaAgent(model_dir=args.model_dir)
    results = run_invariance_test(agent, sampled, args.permutations_per_state)

    out_path = Path(args.out) if args.out else logs_dir / "invariance_test.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = summarize(results)
    (out_path.parent / "invariance_test_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))
    print(f"Full results written to {out_path}")


if __name__ == "__main__":
    main()
