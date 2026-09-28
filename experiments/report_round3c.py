#!/usr/bin/env python3
"""Generate round-3C direct-choice comparison from logs_round3c."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List

from experiments.stats import compare_to_baseline

VARIANTS = ("rules", "julia_direct_choice", "laya_direct_choice")
LOGS = Path("logs_round3c")
OUT = Path("reports/round3c_report.md")


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def avg(rows: Iterable[dict], key: str) -> float:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return mean(values) if values else 0.0


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
        if int((row.get("round3c_trace") or {}).get("model_calls", 0)) > 0
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


def routing_counts(rows: List[dict]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        trace = row.get("round3c_trace") or {}
        for metadata in trace.get("backend_metadata") or []:
            routing = metadata.get("routing") or {}
            model = routing.get("model")
            if model:
                counts[str(model)] += 1
    return counts


def fmt_ci(comparison) -> str:
    if comparison.mean_diff is None:
        return "n/d"
    low = "n/d" if comparison.ci95_low is None else f"{comparison.ci95_low:.2f}"
    high = "n/d" if comparison.ci95_high is None else f"{comparison.ci95_high:.2f}"
    flag = "significativo" if comparison.significant else "não significativo"
    return (
        f"{comparison.mean_diff:+.2f} [{low}, {high}] "
        f"({flag}, n={comparison.n_pairs})"
    )


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
        raise SystemExit(f"Missing round-3C results for: {', '.join(missing)}")

    lines = [
        "# Relatório rodada 3C: direct choice Julia-1 vs Laya no VizDoom",
        "",
        "Cada modelo recebe uma única pergunta choice sobre as ações atualmente "
        "válidas. Não existem gates booleanos, survival_priority ou thresholds "
        "ajustados ao benchmark.",
        "",
        "## Resultados agregados",
        "",
        "| Métrica | regras | Julia direct choice | Laya direct choice |",
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
        ("Fallbacks/episódio", "fallback_steps"),
    ]
    for label, key in metric_rows:
        values = [avg(summaries[variant], key) for variant in VARIANTS]
        if key in {"cache_hit_rate", "attack_rate_when_available"}:
            rendered = [f"{value:.1%}" for value in values]
        else:
            rendered = [f"{value:.2f}" for value in values]
        lines.append(
            f"| {label} | {rendered[0]} | {rendered[1]} | {rendered[2]} |"
        )

    julia_lat = model_refresh_latencies(decisions["julia_direct_choice"])
    laya_lat = model_refresh_latencies(decisions["laya_direct_choice"])
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
        "| Ação | regras | Julia direct choice | Laya direct choice |",
        "|---|---:|---:|---:|",
    ]
    for action in actions:
        lines.append(
            f"| {action} | {action_counts['rules'][action]} | "
            f"{action_counts['julia_direct_choice'][action]} | "
            f"{action_counts['laya_direct_choice'][action]} |"
        )

    routes = routing_counts(decisions["laya_direct_choice"])
    lines += [
        "",
        "## Sanity checks",
        "",
        "- Roteamento Laya observado: "
        + (
            ", ".join(f"{key}={value}" for key, value in routes.items())
            if routes
            else "n/d"
        ),
        f"- Julia ataques executados: {action_counts['julia_direct_choice']['atacar']}",
        f"- Laya ataques executados: {action_counts['laya_direct_choice']['atacar']}",
        "",
        "## Comparação pareada vs regras (IC 95%)",
        "",
    ]

    baseline = summaries["rules"]
    for variant in ("julia_direct_choice", "laya_direct_choice"):
        lines.append(f"### {variant}")
        lines.append("")
        for metric, direction in (
            ("survival_seconds", "higher_is_better"),
            ("kills", "higher_is_better"),
            ("damage_taken", "lower_is_better"),
            ("ammo_consumed", "lower_is_better"),
        ):
            comparison = compare_to_baseline(
                metric,
                by_seed(baseline, metric),
                by_seed(summaries[variant], metric),
                direction,
            )
            lines.append(f"- {metric}: {fmt_ci(comparison)}")
        lines.append("")

    lines += [
        "## Metodologia",
        "",
        "- A seleção de ação é modelada como choice porque as ações são mutuamente exclusivas.",
        "- Julia usa o checkpoint Julia-1 com strict_encoding=True.",
        "- Laya usa Router automático no benchmark em inglês.",
        "- Ambos recebem o mesmo estado estruturado, ações válidas e descrições.",
        "- Ordem dos candidatos fixa; sem embaralhamento.",
        "- Nenhuma probabilidade é usada para gate ou fallback por threshold.",
        "- Só erros de inferência usam fallback determinístico.",
        "- O executor VizDoom é idêntico nos três agentes.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
