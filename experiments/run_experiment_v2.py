#!/usr/bin/env python3
"""Round 2: rules, julia_raw, julia_filtered, julia_filtered_fallback.

This is a separate script from ``run_experiment.py`` (round 1) on purpose:
round 1's results must not change, and its script must keep reproducing them
exactly as documented in docs/REPRODUCE.md. Round 2 adds a deterministic
pre-filter, a per-action anti-loop leash, a rule-agent "shadow" decision
logged alongside every real one (for agreement analysis), and phase-tagged
seeds. Run once per variant (see docs/REPRODUCE_ROUND2.md).

Usage:
    python experiments/run_experiment_v2.py --variant rules
    python experiments/run_experiment_v2.py --variant julia_raw
    python experiments/run_experiment_v2.py --variant julia_filtered
    python experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.75
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List, Tuple

from decision.actions import Action
from decision.agents.anti_loop import AntiLoopGuard
from decision.agents.base import DecisionAgent
from decision.agents.fallback import JuliaWithFallbackAgent
from decision.agents.filter import ActionFilterGuard
from decision.agents.julia import JuliaAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.logging import DecisionLogger
from vizdoom_env.wrapper import VizDoomEnv

VARIANT_CHOICES = ("rules", "julia_raw", "julia_filtered", "julia_filtered_fallback")


def parse_seed_range(spec: str) -> List[int]:
    """Parses "1000-1019" (inclusive) or a single "1000" into a seed list."""
    spec = spec.strip()
    if not spec:
        return []
    if "-" in spec:
        start_s, end_s = spec.split("-", 1)
        return list(range(int(start_s), int(end_s) + 1))
    return [int(spec)]


def variant_dir_name(variant: str, confidence_threshold: float) -> str:
    if variant == "julia_filtered_fallback":
        return f"{variant}_t{int(round(confidence_threshold * 100)):02d}"
    return variant


def build_agent(
    variant: str,
    confidence_threshold: float,
    model_dir: str,
    max_repeat: int,
    wait_max_repeat: int,
) -> DecisionAgent:
    action_max_repeat = {Action.WAIT: wait_max_repeat}

    if variant == "rules":
        base: DecisionAgent = RuleBasedAgent()
    elif variant == "julia_raw":
        base = JuliaAgent(model_dir=model_dir)
    elif variant == "julia_filtered":
        base = ActionFilterGuard(JuliaAgent(model_dir=model_dir))
    elif variant == "julia_filtered_fallback":
        base = JuliaWithFallbackAgent(
            julia_agent=ActionFilterGuard(JuliaAgent(model_dir=model_dir)),
            fallback_agent=RuleBasedAgent(),
            confidence_threshold=confidence_threshold,
        )
    else:
        raise ValueError(f"Unknown variant: {variant}")

    return AntiLoopGuard(base, max_repeat=max_repeat, action_max_repeat=action_max_repeat)


def run_episode(
    variant_label: str,
    agent: DecisionAgent,
    rule_shadow: RuleBasedAgent,
    seed: int,
    phase: str,
    frame_skip: int,
    episode_timeout: int,
    max_decisions: int,
    logger: DecisionLogger,
) -> dict:
    env = VizDoomEnv(frame_skip=frame_skip, episode_timeout=episode_timeout, seed=seed)
    agent.reset()
    try:
        state = env.reset()
        info = {"kills": 0, "damage_taken": 0.0, "ammo_consumed_total": 0, "tics_elapsed": 0}
        step = 0
        while step < max_decisions:
            available = env.compute_available_actions(state)
            decision = agent.decide(state, available)
            # Shadow decision: what the deterministic baseline would have
            # done from the exact same (state, available_actions), purely
            # for the "concordância com regras" diagnostic -- never affects
            # what actually gets executed.
            shadow_action = rule_shadow.decide(state, available).action
            exec_action = decision.action if decision.action in available else Action.WAIT

            logger.log(
                agent_variant=variant_label,
                episode_id=seed,
                step=step,
                state=state,
                available_actions=available,
                decision=decision,
                extra={"phase": phase, "seed": seed, "rule_shadow_action": shadow_action.value},
            )

            new_state, done, info = env.step(exec_action)
            step += 1
            if done:
                break
            state = new_state

        died = info["tics_elapsed"] < (episode_timeout - frame_skip)
        return {
            "agent_variant": variant_label,
            "phase": phase,
            "episode_id": seed,
            "seed": seed,
            "survival_tics": info["tics_elapsed"],
            "survival_seconds": info["tics_elapsed"] / 35.0,
            "kills": info["kills"],
            "damage_taken": info["damage_taken"],
            "ammo_consumed": info["ammo_consumed_total"],
            "died": died,
        }
    finally:
        env.close()


def seeds_with_phase(seeds_a: List[int], seeds_b: List[int]) -> List[Tuple[int, str]]:
    tagged = [(s, "A") for s in seeds_a] + [(s, "B") for s in seeds_b]
    overlap = set(seeds_a) & set(seeds_b)
    if overlap:
        raise ValueError(f"Seeds {sorted(overlap)} appear in both phase A and phase B")
    return tagged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True, choices=VARIANT_CHOICES)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--seeds-a", type=str, default="1000-1019")
    parser.add_argument("--seeds-b", type=str, default="5000-5029")
    parser.add_argument("--frame-skip", type=int, default=8)
    parser.add_argument("--episode-timeout", type=int, default=2400)
    parser.add_argument("--max-repeat", type=int, default=5)
    parser.add_argument(
        "--wait-max-repeat",
        type=int,
        default=3,
        help="Tighter anti-loop leash specifically for 'esperar' (round 1 found "
        "Julia defaults to it far more than the rule baseline).",
    )
    parser.add_argument("--model-dir", type=str, default="models/Julia-1")
    parser.add_argument("--out-dir", type=str, default="logs_round2")
    args = parser.parse_args()

    seeds_a = parse_seed_range(args.seeds_a)
    seeds_b = parse_seed_range(args.seeds_b)
    tagged_seeds = seeds_with_phase(seeds_a, seeds_b)

    max_decisions = args.episode_timeout // args.frame_skip + 20
    label = variant_dir_name(args.variant, args.confidence_threshold)

    out_dir = Path(args.out_dir)
    variant_dir = out_dir / label
    variant_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = variant_dir / "decisions.jsonl"
    summary_path = variant_dir / "episodes_summary.jsonl"
    decisions_path.unlink(missing_ok=True)  # start each run from a clean file

    run_meta = {
        "started_at": time.time(),
        "variant": args.variant,
        "label": label,
        "confidence_threshold": args.confidence_threshold if args.variant == "julia_filtered_fallback" else None,
        "seeds_a": seeds_a,
        "seeds_b": seeds_b,
        "frame_skip": args.frame_skip,
        "episode_timeout": args.episode_timeout,
        "max_repeat": args.max_repeat,
        "wait_max_repeat": args.wait_max_repeat,
    }
    (variant_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

    print(f"=== round 2 variant: {label} ({len(tagged_seeds)} episodes) ===")
    agent = build_agent(
        args.variant, args.confidence_threshold, args.model_dir, args.max_repeat, args.wait_max_repeat
    )
    rule_shadow = RuleBasedAgent()

    with DecisionLogger(decisions_path) as logger, summary_path.open("w", encoding="utf-8") as summary_file:
        for seed, phase in tagged_seeds:
            t0 = time.time()
            summary = run_episode(
                variant_label=label,
                agent=agent,
                rule_shadow=rule_shadow,
                seed=seed,
                phase=phase,
                frame_skip=args.frame_skip,
                episode_timeout=args.episode_timeout,
                max_decisions=max_decisions,
                logger=logger,
            )
            summary_file.write(json.dumps(summary) + "\n")
            summary_file.flush()
            elapsed = time.time() - t0
            print(
                f"  [{phase}] seed={seed} survival_s={summary['survival_seconds']:.1f} "
                f"kills={summary['kills']} damage={summary['damage_taken']:.0f} "
                f"died={summary['died']} ({elapsed:.1f}s wall)"
            )

    print(f"Done. Logs written under {variant_dir}/")


if __name__ == "__main__":
    main()
