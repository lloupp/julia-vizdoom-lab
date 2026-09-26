#!/usr/bin/env python3
"""Generates reports/comparative_report.md straight from the JSONL logs.

Does not accept any manually-entered numbers: every figure in the report is
computed here from logs/<variant>/decisions.jsonl and episodes_summary.jsonl,
which run_experiment.py wrote directly from the running episodes.

Usage:
    python experiments/report.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from experiments.metrics import aggregate_variant, compute_episode_metrics, load_jsonl

VARIANT_LABELS = {
    "rules": "Somente regras (baseline)",
    "julia": "Julia-1 (puro)",
    "julia_fallback": "Julia-1 + fallback",
}

METRIC_ROWS = [
    ("survival_seconds", "Tempo de sobrevivência (s)", "{:.1f}", "higher"),
    ("kills", "Inimigos eliminados", "{:.2f}", "higher"),
    ("damage_taken", "Dano recebido", "{:.1f}", "lower"),
    ("ammo_consumed", "Munição consumida", "{:.1f}", "lower"),
    ("decisions", "Decisões por episódio", "{:.1f}", "context"),
    ("avg_confidence", "Confiança média (ação executada)", "{:.3f}", "context"),
    ("avg_model_confidence", "Confiança média do modelo Julia-1", "{:.3f}", "context"),
    ("fallback_count", "Fallbacks (baixa confiança) por episódio", "{:.2f}", "context"),
    ("fallback_rate", "Taxa de fallback (baixa confiança)", "{:.1%}", "context"),
    ("antiloop_override_count", "Quebras de loop por episódio", "{:.2f}", "context"),
    ("avg_latency_ms", "Latência média do Julia-1 (ms)", "{:.2f}", "lower"),
    ("p95_latency_ms", "Latência p95 do Julia-1 (ms)", "{:.2f}", "lower"),
    ("error_count", "Erros do modelo por episódio", "{:.2f}", "lower"),
    ("invalid_action_count", "Decisões inválidas por episódio", "{:.2f}", "lower"),
    ("death_rate", "Taxa de morte (vs. timeout)", "{:.1%}", "lower"),
]


def load_variant_episode_metrics(logs_dir: Path, variant: str) -> List[dict]:
    variant_dir = logs_dir / variant
    decisions = load_jsonl(variant_dir / "decisions.jsonl")
    summaries = load_jsonl(variant_dir / "episodes_summary.jsonl")

    by_episode: Dict[int, List[dict]] = {}
    for d in decisions:
        by_episode.setdefault(d["episode_id"], []).append(d)

    episode_metrics = []
    for summary in summaries:
        eid = summary["episode_id"]
        episode_metrics.append(compute_episode_metrics(by_episode.get(eid, []), summary))
    return episode_metrics


def format_cell(value: Optional[float], fmt: str) -> str:
    if value is None:
        return "n/d"
    return fmt.format(value)


def pct_change(baseline: Optional[float], other: Optional[float]) -> Optional[float]:
    if baseline is None or other is None or baseline == 0:
        return None
    return (other - baseline) / abs(baseline) * 100.0


def render_report(logs_dir: Path, variants: List[str]) -> str:
    aggregates: Dict[str, dict] = {}
    for variant in variants:
        episode_metrics = load_variant_episode_metrics(logs_dir, variant)
        aggregates[variant] = aggregate_variant(episode_metrics)

    run_meta = {}
    meta_path = logs_dir / "run_meta.json"
    if meta_path.exists():
        run_meta = json.loads(meta_path.read_text())

    lines = []
    lines.append("# Relatório comparativo: Julia-1 vs. baseline de regras (VizDoom)")
    lines.append("")
    lines.append(
        "Relatório gerado automaticamente a partir dos logs em "
        f"`{logs_dir}/<variant>/decisions.jsonl` e `episodes_summary.jsonl`. "
        "Nenhum número abaixo foi editado manualmente."
    )
    lines.append("")
    if run_meta:
        lines.append("## Configuração do experimento")
        lines.append("")
        for k, v in run_meta.items():
            if k == "started_at":
                continue
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    lines.append("## Métricas agregadas por variante")
    lines.append("")
    header = "| Métrica | " + " | ".join(VARIANT_LABELS.get(v, v) for v in variants) + " |"
    sep = "|---" * (len(variants) + 1) + "|"
    lines.append(header)
    lines.append(sep)
    for field, label, fmt, _direction in METRIC_ROWS:
        row = [label]
        for variant in variants:
            row.append(format_cell(aggregates.get(variant, {}).get(field), fmt))
        lines.append("| " + " | ".join(row) + " |")
    n_episodes = {v: aggregates.get(v, {}).get("episodes") for v in variants}
    lines.append("| Episódios avaliados | " + " | ".join(str(n_episodes[v] or 0) for v in variants) + " |")
    lines.append("")

    if "rules" in variants:
        lines.append("## Julia-1 melhora ou piora o agente, comparado ao baseline?")
        lines.append("")
        lines.append(
            "Variação percentual em relação ao baseline determinístico "
            "(`somente regras`); positivo = variante ficou acima do baseline."
        )
        lines.append("")
        compare_targets = [v for v in variants if v != "rules"]
        header2 = "| Métrica | " + " | ".join(f"Δ% {VARIANT_LABELS.get(v, v)}" for v in compare_targets) + " |"
        lines.append(header2)
        lines.append("|---" * (len(compare_targets) + 1) + "|")
        for field, label, _fmt, direction in METRIC_ROWS:
            if direction == "context":
                continue
            baseline_value = aggregates.get("rules", {}).get(field)
            row = [label]
            for variant in compare_targets:
                other_value = aggregates.get(variant, {}).get(field)
                delta = pct_change(baseline_value, other_value)
                if delta is None:
                    row.append("n/d")
                else:
                    better = (direction == "higher" and delta > 0) or (direction == "lower" and delta < 0)
                    arrow = "▲ melhor" if better else ("▼ pior" if abs(delta) > 1e-9 else "≈ igual")
                    row.append(f"{delta:+.1f}% ({arrow})")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

        lines.append("### Síntese objetiva")
        lines.append("")
        for variant in compare_targets:
            wins, losses, ties = [], [], []
            for field, label, _fmt, direction in METRIC_ROWS:
                if direction == "context":
                    continue
                baseline_value = aggregates.get("rules", {}).get(field)
                other_value = aggregates.get(variant, {}).get(field)
                delta = pct_change(baseline_value, other_value)
                if delta is None or abs(delta) < 1e-9:
                    ties.append(label)
                    continue
                better = (direction == "higher" and delta > 0) or (direction == "lower" and delta < 0)
                (wins if better else losses).append(label)
            lines.append(
                f"**{VARIANT_LABELS.get(variant, variant)}** vs. baseline: "
                f"melhora em {len(wins)} métrica(s) ({', '.join(wins) if wins else '-'}), "
                f"piora em {len(losses)} métrica(s) ({', '.join(losses) if losses else '-'}), "
                f"empata em {len(ties)}."
            )
        lines.append("")
        lines.append(
            "Contagem simples de métricas com direção definida (sobrevivência, "
            "kills, dano, munição, latência, erros, decisões inválidas, taxa "
            "de morte); não pondera a importância relativa de cada métrica "
            "para o caso de uso final -- essa ponderação cabe a quem for "
            "decidir se usa Julia-1 em produção."
        )
        lines.append("")

    lines.append("## Notas de metodologia")
    lines.append("")
    lines.append(
        "- Cada episódio de cada variante usa a mesma seed pareada "
        "(`seed_base + episode_id`), controlando a condição inicial do VizDoom "
        "entre variantes; a partir do momento em que as decisões divergem, os "
        "estados do jogo naturalmente divergem também -- isso é o que está "
        "sendo medido."
    )
    lines.append(
        "- 'Confiança média (ação executada)' é 1.0 por definição para o "
        "baseline de regras (regras determinísticas não têm incerteza); a "
        "coluna 'Confiança média do modelo Julia-1' é a única comparável "
        "entre as variantes que usam o modelo."
    )
    lines.append(
        "- Latência do Julia-1 é medida por chamada real a `engine.predict(...)`"
        " rodando localmente em CPU; o baseline de regras não tem essa coluna "
        "por não invocar o modelo."
    )
    lines.append(
        "- 'Fallbacks (baixa confiança)' e 'Quebras de loop' são mecanismos "
        "independentes: o primeiro só existe em `julia_fallback` (confiança "
        "do modelo abaixo do threshold); o segundo (`AntiLoopGuard`) é aplicado "
        "igualmente às 3 variantes para evitar loops infinitos, por isso pode "
        "aparecer também no baseline de regras."
    )
    lines.append(
        "- 'Munição' é a munição da arma atualmente equipada (`SELECTED_WEAPON_AMMO`)."
        " O Doom troca de arma automaticamente ao pegar uma nova (comportamento "
        "padrão do motor); quando isso acontece, o valor de munição salta para o "
        "pool da nova arma. 'Munição consumida' ignora esses saltos (só conta "
        "quedas enquanto a arma equipada não muda), para não confundir troca de "
        "arma com disparo real."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=str, default="logs")
    parser.add_argument("--out", type=str, default="reports/comparative_report.md")
    parser.add_argument(
        "--variants", type=str, default="rules,julia,julia_fallback"
    )
    args = parser.parse_args()

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    report = render_report(Path(args.logs_dir), variants)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
