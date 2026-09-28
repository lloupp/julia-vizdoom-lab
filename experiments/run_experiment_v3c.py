#!/usr/bin/env python3
"""Round 3C: rules vs Julia-1 vs Laya using one direct typed action choice."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple

from decision.actions import Action
from decision.agents.anti_loop import AntiLoopGuard
from decision.agents.base import DecisionAgent
from decision.agents.rule_based import RuleBasedAgent
from decision.logging import DecisionLogger
from round3.backends import JuliaBackend
from round3b.backends import LayaRecommendedBackend
from round3c.agent import DirectChoiceAgent
from vizdoom_env.wrapper import VizDoomEnv

VARIANTS = ("rules", "julia_direct_choice", "laya_direct_choice")


def parse_seed_range(spec: str) -> List[int]:
    spec = spec.strip()
    if not spec:
        return []
    if "-" in spec:
        start_s, end_s = spec.split("-", 1)
        return list(range(int(start_s), int(end_s) + 1))
    return [int(spec)]


def seeds_with_phase(seeds_a: List[int], seeds_b: List[int]) -> List[Tuple[int, str]]:
    overlap = set(seeds_a) & set(seeds_b)
    if overlap:
        raise ValueError(f"Seeds {sorted(overlap)} appear in both phases")
    return [(s, "A") for s in seeds_a] + [(s, "B") for s in seeds_b]


def build_agent(
    variant: str,
    *,
    julia_model_dir: str,
    max_hold_steps: int,
    max_repeat: int,
    wait_max_repeat: int,
) -> tuple[DecisionAgent, DirectChoiceAgent | None]:
    trace_source: DirectChoiceAgent | None = None

    if variant == "rules":
        base: DecisionAgent = RuleBasedAgent()
    elif variant == "julia_direct_choice":
        trace_source = DirectChoiceAgent(
            JuliaBackend(model_dir=julia_model_dir),
            max_hold_steps=max_hold_steps,
        )
        base = trace_source
    elif variant == "laya_direct_choice":
        trace_source = DirectChoiceAgent(
            LayaRecommendedBackend(preload=False),
            max_hold_steps=max_hold_steps,
        )
        base = trace_source
    else:
        raise ValueError(f"Unknown variant: {variant}")

    return (
        AntiLoopGuard(
            base,
            max_repeat=max_repeat,
            action_max_repeat={Action.WAIT: wait_max_repeat},
        ),
        trace_source,
    )


def run_episode(
    variant: str,
    agent: DecisionAgent,
    trace_source: DirectChoiceAgent | None,
    seed: int,
    phase: str,
    frame_skip: int,
    episode_timeout: int,
    max_decisions: int,
    logger: DecisionLogger,
) -> dict:
    env = VizDoomEnv(frame_skip=frame_skip, episode_timeout=episode_timeout, seed=seed)
    agent.reset()
    model_calls_total = 0
    cache_hits = 0
    stage_counts: Counter = Counter()
    attack_available_steps = 0
    attack_executed_steps = 0
    fallback_steps = 0

    try:
        state = env.reset()
        info = {
            "kills": 0,
            "damage_taken": 0.0,
            "ammo_consumed_total": 0,
            "tics_elapsed": 0,
        }
        step = 0

        while step < max_decisions:
            available = env.compute_available_actions(state)
            decision = agent.decide(state, available)
            trace = dict(trace_source.last_trace) if trace_source is not None else {
                "backend": "rules",
                "cache_hit": False,
                "model_calls": 0,
                "stage": "rules",
                "candidate_count": len(available),
                "score_kind": "deterministic",
                "score_is_calibrated": True,
                "backend_metadata": [],
            }

            model_calls_total += int(trace.get("model_calls", 0))
            cache_hits += int(bool(trace.get("cache_hit")))
            stage_counts[str(trace.get("stage", "unknown"))] += 1
            fallback_steps += int(bool(decision.fallback_used))

            if Action.ATTACK in available:
                attack_available_steps += 1

            exec_action = decision.action if decision.action in available else Action.WAIT
            if exec_action == Action.ATTACK:
                attack_executed_steps += 1

            logger.log(
                agent_variant=variant,
                episode_id=seed,
                step=step,
                state=state,
                available_actions=available,
                decision=decision,
                extra={"phase": phase, "seed": seed, "round3c_trace": trace},
            )

            new_state, done, info = env.step(exec_action)
            step += 1
            if done:
                break
            state = new_state

        died = info["tics_elapsed"] < (episode_timeout - frame_skip)
        return {
            "agent_variant": variant,
            "phase": phase,
            "episode_id": seed,
            "seed": seed,
            "survival_tics": info["tics_elapsed"],
            "survival_seconds": info["tics_elapsed"] / 35.0,
            "kills": info["kills"],
            "damage_taken": info["damage_taken"],
            "ammo_consumed": info["ammo_consumed_total"],
            "died": died,
            "decisions": step,
            "model_calls": model_calls_total,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hits / step if step else 0.0,
            "stage_counts": dict(stage_counts),
            "fallback_steps": fallback_steps,
            "attack_available_steps": attack_available_steps,
            "attack_executed_steps": attack_executed_steps,
            "attack_rate_when_available": (
                attack_executed_steps / attack_available_steps
                if attack_available_steps
                else 0.0
            ),
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True, choices=VARIANTS)
    parser.add_argument("--seeds-a", default="1000-1019")
    parser.add_argument("--seeds-b", default="7000-7029")
    parser.add_argument("--frame-skip", type=int, default=8)
    parser.add_argument("--episode-timeout", type=int, default=2400)
    parser.add_argument("--max-hold-steps", type=int, default=4)
    parser.add_argument("--max-repeat", type=int, default=5)
    parser.add_argument("--wait-max-repeat", type=int, default=3)
    parser.add_argument("--julia-model-dir", default="models/Julia-1")
    parser.add_argument("--out-dir", default="logs_round3c")
    args = parser.parse_args()

    tagged = seeds_with_phase(
        parse_seed_range(args.seeds_a),
        parse_seed_range(args.seeds_b),
    )

    out_dir = Path(args.out_dir) / args.variant
    out_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = out_dir / "decisions.jsonl"
    summaries_path = out_dir / "episodes_summary.jsonl"
    decisions_path.unlink(missing_ok=True)

    meta = {
        "started_at": time.time(),
        "variant": args.variant,
        "seeds_a": args.seeds_a,
        "seeds_b": args.seeds_b,
        "frame_skip": args.frame_skip,
        "episode_timeout": args.episode_timeout,
        "max_hold_steps": args.max_hold_steps,
        "decision_protocol": "single direct choice over valid actions",
        "candidate_order": "fixed decision.actions.ALL_ACTIONS order",
        "laya_router": "automatic English/general routing",
        "julia_confidence_gate": False,
        "laya_confidence_gate": False,
        "boolean_gates": False,
    }
    (out_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )

    print(f"=== round 3C: {args.variant} ({len(tagged)} episodes) ===")
    agent, trace_source = build_agent(
        args.variant,
        julia_model_dir=args.julia_model_dir,
        max_hold_steps=args.max_hold_steps,
        max_repeat=args.max_repeat,
        wait_max_repeat=args.wait_max_repeat,
    )

    max_decisions = args.episode_timeout // args.frame_skip + 20
    with DecisionLogger(decisions_path) as logger, summaries_path.open(
        "w", encoding="utf-8"
    ) as out:
        for seed, phase in tagged:
            started = time.time()
            summary = run_episode(
                args.variant,
                agent,
                trace_source,
                seed,
                phase,
                args.frame_skip,
                args.episode_timeout,
                max_decisions,
                logger,
            )
            out.write(json.dumps(summary) + "\n")
            out.flush()
            print(
                f"  [{phase}] seed={seed} survival={summary['survival_seconds']:.1f}s "
                f"kills={summary['kills']} calls={summary['model_calls']} "
                f"attack_rate={summary['attack_rate_when_available']:.1%} "
                f"wall={time.time()-started:.1f}s"
            )

    print(f"Done: {out_dir}")


if __name__ == "__main__":
    main()
