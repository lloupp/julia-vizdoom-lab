#!/usr/bin/env python3
"""Generate the round-3 comparison directly from its raw logs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List

from experiments.stats import compare_to_baseline

VARIANTS = ("rules", "julia_recommended", "laya_recommended")
OUT = Path("reports/round3_report.md")


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def avg(rows: Iterable[dict], key: str) -> float:
    vals = [float(row[key]) for row in rows if row.get(key) is not None]
    return mean(vals) if vals else 0.0


def by_seed(rows: List[dict], key: str) -> Dict[int, float]:
    return {int(row["seed"]): float(row[key]) for row in rows if row.get(key) is not None}


def fmt_ci(c) -> str:
    if c.mean_diff is None:
        return "n/d"
    lo = "n/d" if c.ci95_low is None else f"{c.ci95_low:.2f}"
    hi = "n/d" if c.ci95_high is None else f"{c.ci95_high:.2f}"
    flag = "significativo" if c.significant else "não significativo"
    return f"{c.mean_diff:+.2f} [{lo}, {hi}] ({flag}, n={c.n_pairs})"


def main() -> None:
    summaries = {
        v: read_jsonl(Path("logs_round3") / v / "episodes_summary.jsonl")
        for v in VARIANTS
    }
    decisions = {
        v: read_jsonl(Path("logs_round3") / v / "decisions.jsonl")
        for v in VARIANTS
    }
    missing = [v for v in VARIANTS if not summaries[v]]
    if missing:
        raise SystemExit(f"Missing round-3 results for: {', '.join(missing)}")

    lines = [
        "# Relatório rodada 3: Julia-1 vs Laya no VizDoom",
        "",
        "Gerado somente a partir de logs_round3/. A rodada usa o mesmo ambiente, "
        "estado, ações, seeds, hierarquia noul -> choice, ordem fixa de candidatos "
        "e política orientada a eventos para os dois modelos.",
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
    ]
    for label, key in metric_rows:
        vals = [avg(summaries[v], key) for v in VARIANTS]
        rendered = [f"{x:.1%}" for x in vals] if key == "cache_hit_rate" else [f"{x:.2f}" for x in vals]
        lines.append(f"| {label} | {rendered[0]} | {rendered[1]} | {rendered[2]} |")

    lines += ["", "## Ações executadas", ""]
    action_counts = {v: Counter(row["action"] for row in decisions[v]) for v in VARIANTS}
    actions = sorted(set().union(*(set(c) for c in action_counts.values())))
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
        "## Metodologia relevante",
        "",
        "- Julia usa a API de perguntas nomeadas com strict_encoding=True.",
        "- Laya usa Router com override explícito model=typed-decisions.",
        "- Perguntas Boolean noul têm descrições explícitas para false e true.",
        "- As quatro perguntas Boolean são avaliadas em lote; depois há no máximo uma pequena choice.",
        "- A ordem de candidatos é fixa e semântica. Não há embaralhamento durante o benchmark.",
        "- max_probability da Julia é registrado como score bruto e não é usado como confiança calibrada nem como gate de fallback.",
        "- O modelo só é consultado em mudança estratégica de estado ou após expirar a janela de cache.",
        "- Regras, Julia e Laya executam exatamente o mesmo executor determinístico do VizDoom.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
