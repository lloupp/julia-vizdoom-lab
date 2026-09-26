#!/usr/bin/env python3
"""Runs the 3-way comparison: rules-only, Julia-1-only, Julia-1+fallback.

Each variant plays the same paired seeds (same seed => same VizDoom initial
conditions) so environment randomness is controlled for as far as possible;
once agents make different choices the game states necessarily diverge,
which is exactly what we are measuring.

Usage:
    python experiments/run_experiment.py --episodes 12
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import List

from decision.actions import Action
from decision.agents.anti_loop import AntiLoopGuard
from decision.agents.base import DecisionAgent
from decision.agents.fallback import JuliaWithFallbackAgent
from decision.agents.julia import JuliaAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.logging import DecisionLogger
from vizdoom_env.wrapper import VizDoomEnv

VARIANTS = ("rules", "julia", "julia_fallback")


def build_agent(variant: str, confidence_threshold: float, model_dir: str) -> DecisionAgent:
    if variant == "rules":
        base: DecisionAgent = RuleBasedAgent()
    elif variant == "julia":
        base = JuliaAgent(model_dir=model_dir)
    elif variant == "julia_fallback":
        base = JuliaWithFallbackAgent(
            julia_agent=JuliaAgent(model_dir=model_dir),
            fallback_agent=RuleBasedAgent(),
            confidence_threshold=confidence_threshold,
        )
    else:
        raise ValueError(f"Unknown variant: {variant}")
    return AntiLoopGuard(base)


def run_episode(
    variant: str,
    agent: DecisionAgent,
    episode_id: int,
    seed: int,
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
            exec_action = decision.action if decision.action in available else Action.WAIT

            logger.log(
                agent_variant=variant,
                episode_id=episode_id,
                step=step,
                state=state,
                available_actions=available,
                decision=decision,
            )

            new_state, done, info = env.step(exec_action)
            step += 1
            if done:
                break
            state = new_state

        died = info["tics_elapsed"] < (episode_timeout - frame_skip)
        return {
            "agent_variant": variant,
            "episode_id": episode_id,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episodes", type=int, default=12)
    parser.add_argument("--seed-base", type=int, default=1000)
    parser.add_argument("--frame-skip", type=int, default=8)
    parser.add_argument("--episode-timeout", type=int, default=1500)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--model-dir", type=str, default="models/Julia-1")
    parser.add_argument("--out-dir", type=str, default="logs")
    parser.add_argument(
        "--variants",
        type=str,
        default=",".join(VARIANTS),
        help="Comma-separated subset of: rules,julia,julia_fallback",
    )
    args = parser.parse_args()

    variants: List[str] = [v.strip() for v in args.variants.split(",") if v.strip()]
    max_decisions = args.episode_timeout // args.frame_skip + 20

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_meta = {
        "started_at": time.time(),
        "episodes_per_variant": args.episodes,
        "seed_base": args.seed_base,
        "frame_skip": args.frame_skip,
        "episode_timeout": args.episode_timeout,
        "confidence_threshold": args.confidence_threshold,
        "variants": variants,
    }
    (out_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

    for variant in variants:
        print(f"=== variant: {variant} ===")
        agent = build_agent(variant, args.confidence_threshold, args.model_dir)
        variant_dir = out_dir / variant
        decisions_path = variant_dir / "decisions.jsonl"
        summary_path = variant_dir / "episodes_summary.jsonl"
        variant_dir.mkdir(parents=True, exist_ok=True)
        # DecisionLogger appends; start each run from a clean file so a
        # re-run never mixes stale decisions with the new ones.
        decisions_path.unlink(missing_ok=True)

        with DecisionLogger(decisions_path) as logger, summary_path.open("w", encoding="utf-8") as summary_file:
            for episode_id in range(args.episodes):
                seed = args.seed_base + episode_id
                t0 = time.time()
                summary = run_episode(
                    variant=variant,
                    agent=agent,
                    episode_id=episode_id,
                    seed=seed,
                    frame_skip=args.frame_skip,
                    episode_timeout=args.episode_timeout,
                    max_decisions=max_decisions,
                    logger=logger,
                )
                summary_file.write(json.dumps(summary) + "\n")
                summary_file.flush()
                elapsed = time.time() - t0
                print(
                    f"  episode {episode_id:03d} seed={seed} "
                    f"survival_s={summary['survival_seconds']:.1f} "
                    f"kills={summary['kills']} damage={summary['damage_taken']:.0f} "
                    f"died={summary['died']} ({elapsed:.1f}s wall)"
                )

    print(f"Done. Logs written under {out_dir}/<variant>/")


if __name__ == "__main__":
    main()
