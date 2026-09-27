#!/usr/bin/env python3
"""Generate the model-native round-3B report from logs_round3b only."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List

from experiments.stats import compare_to_baseline

VARIANTS = ("rules", "julia_recommended", "laya_recommended")
LOGS = Path("logs_round3b")
OUT = Path("reports/round3b_report.md")


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def avg(rows: Iterable[dict], key: str) -> float:
    vals = [float(row[key]) for row in rows if row.get(key) is not None]
    return mean(vals) if vals else 0.0


def by_seed(rows: List[dict], key: str) -> Dict[int, float]:
    return {
        int(row["seed"]): float(row[key])
        for row in rows
        if row.get(key) is not None
    }


def model_refresh_latencies(rows: List[dict]) -> List[float]:
    return [
        float(row["latency_ms"])
        for row in rows
        if int((row.get("round3b_trace") or {}).get("model_calls", 0)) > 0
    ]


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    data = sorted(values)
    idx = (len(data) - 1) * p
    lo = int(idx)
    hi = min(lo + 1, len(data) - 1)
    frac = idx - lo
    return data[lo] + (data[hi] - data[lo]) * frac


def positive_boolean_rate(rows: List[dict], key: str) -> float:
    values = []
    for row in rows:
        trace = row.get("round3b_trace") or {}
        probs = trace.get("boolean_probabilities") or {}
        if key in probs:
            values.append(float(probs[key]) >= 0.5)
    return mean([1.0 if value else 0.0 for value in values]) if values else 0.0


def routing_counts(rows: List[dict]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        trace = row.get("round3b_trace") or {}
        for metadata in trace.get("backend_metadata") or []:
            routing = metadata.get("routing") or {}
            model = routing.get("model")
            if model:
                counts[str(model)] += 1
    return counts


def fmt_ci(c) -> str:
    if c.mean_diff is None:
        return "n/d"
    lo = "n/d" if c.ci95_low is None else f"{c.ci95_low:.2f}"
    hi = "n/d" if c.ci95_high is None else f"{c.ci95_high:.2f}"
    flag = "significativo" if c.significant else "não significativo"
    return f"{c.mean_diff:+.2f} [{lo}, {hi}] ({flag}, n={c.n_pairs})"


def main() -> None:
    summaries = {
        variant: read_jsonl(LOGS / variant / "episodes_summary.jsonl")
        for variant in VARIANTS
    }
    decisions = {
        variant: read_jsonl(LOGS / variant / "decisions.jsonl")
        for variant in VARIANTS
    }
    missing = [variant for variant in VARIANTS if not summaries[variant]]
    if missing:
        raise SystemExit(f"Missing round-3B results for: {', '.join(missing)}")

    lines = [
        "# Relatório rodada 3B: Julia-1 vs Laya no VizDoom",
        "",
        "O Laya usa Router sem checkpoint especialista forçado e substitui noul por "
        "choice binário com chaves neutras A/B, normalizado de volta para P(true). "
        "Julia mantém noul nativo. O ambiente e o executor permanecem iguais.",
        "",
        "## Resultados agregados",
        "",
        "| Métrica | regras | Julia recomendado | Laya recomendado |",
        "|---|---:|---:|---:|",
    ]

    metric_rows = [
        ("Sobrevivência (s)", "survival_seconds"),
        ("Kills", "kills"),
        ("Dano recebido", "damage_taken"),
        ("Munição consumida", "ammo_consumed"),
        ("Decisões/episódio", "decisions"),
        ("Chamadas de modelo/episódio", "model_calls"),
        ("Cache hit rate", "cache_hit_rate"),
        ("Ataque quando disponível", "attack_rate_when_available"),
    ]
    for label, key in metric_rows:
        vals = [avg(summaries[v], key) for v in VARIANTS]
        if key in {"cache_hit_rate", "attack_rate_when_available"}:
            rendered = [f"{x:.1%}" for x in vals]
        else:
            rendered = [f"{x:.2f}" for x in vals]
        lines.append(
            f"| {label} | {rendered[0]} | {rendered[1]} | {rendered[2]} |"
        )

    julia_lat = model_refresh_latencies(decisions["julia_recommended"])
    laya_lat = model_refresh_latencies(decisions["laya_recommended"])
    lines.append(
        f"| Latência média por refresh (ms) | n/d | "
        f"{(mean(julia_lat) if julia_lat else 0.0):.2f} | "
        f"{(mean(laya_lat) if laya_lat else 0.0):.2f} |"
    )
    lines.append(
        f"| Latência p95 por refresh (ms) | n/d | "
        f"{percentile(julia_lat, 0.95):.2f} | "
        f"{percentile(laya_lat, 0.95):.2f} |"
    )

    lines += ["", "## Ações executadas", ""]
    action_counts = {
        variant: Counter(row["action"] for row in decisions[variant])
        for variant in VARIANTS
    }
    actions = sorted(set().union(*(set(counts) for counts in action_counts.values())))
    lines += [
        "| Ação | regras | Julia recomendado | Laya recomendado |",
        "|---|---:|---:|---:|",
    ]
    for action in actions:
        lines.append(
            f"| {action} | {action_counts['rules'][action]} | "
            f"{action_counts['julia_recommended'][action]} | "
            f"{action_counts['laya_recommended'][action]} |"
        )

    lines += ["", "## Sanity checks do protocolo", ""]
    lines.append(
        f"- Julia engage_enemy positivo: "
        f"{positive_boolean_rate(decisions['julia_recommended'], 'engage_enemy'):.1%}"
    )
    lines.append(
        f"- Laya engage_enemy positivo: "
        f"{positive_boolean_rate(decisions['laya_recommended'], 'engage_enemy'):.1%}"
    )
    routes = routing_counts(decisions["laya_recommended"])
    lines.append(
        "- Roteamento Laya observado: "
        + (", ".join(f"{key}={value}" for key, value in routes.items()) if routes else "n/d")
    )

    lines += ["", "## Comparação pareada vs regras (IC 95%)", ""]
    baseline = summaries["rules"]
    for variant in ("julia_recommended", "laya_recommended"):
        lines.append(f"### {variant}")
        lines.append("")
        for metric, direction in (
            ("survival_seconds", "higher_is_better"),
            ("kills", "higher_is_better"),
            ("damage_taken", "lower_is_better"),
            ("ammo_consumed", "lower_is_better"),
        ):
            c = compare_to_baseline(
                metric,
                by_seed(baseline, metric),
                by_seed(summaries[variant], metric),
                direction,
            )
            lines.append(f"- {metric}: {fmt_ci(c)}")
        lines.append("")

    lines += [
        "## Metodologia",
        "",
        "- Julia: noul nativo + choice, sem usar max_probability como gate.",
        "- Laya: Router automático no benchmark em inglês; nenhum typed-decisions forçado.",
        "- Laya Boolean: choice A/B com descrições yes/no, normalizado para P(true).",
        "- Nenhum threshold foi ajustado olhando os resultados do jogo.",
        "- Ordem dos candidatos permanece fixa por pergunta.",
        "- O executor VizDoom é idêntico nos três agentes.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
