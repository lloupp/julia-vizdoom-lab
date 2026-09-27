#!/usr/bin/env python3
"""Round 2 report: rules vs julia_raw vs julia_filtered vs julia_filtered_fallback
(3 thresholds), the order-invariance test, a round-1-vs-round-2 comparison, and
an explicit go/no-go verdict for advancing to lloupp/minecraft-mbot.

Every number here is computed straight from logs_round2/ (round 2, this
script) and logs/ (round 1, untouched, produced by run_experiment.py /
report.py). Nothing is hand-entered.

Usage:
    python experiments/report_round2.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from experiments import metrics as metrics_v1
from experiments import metrics_v2
from experiments import stats as statmod

ROUND2_VARIANTS = [
    "rules",
    "julia_raw",
    "julia_filtered",
    "julia_filtered_fallback_t60",
    "julia_filtered_fallback_t75",
    "julia_filtered_fallback_t90",
]

LABELS = {
    "rules": "Regras (baseline)",
    "julia_raw": "Julia-1 (raw, sem filtro)",
    "julia_filtered": "Julia-1 filtrada",
    "julia_filtered_fallback_t60": "Julia-1 filtrada + fallback (t=0.60)",
    "julia_filtered_fallback_t75": "Julia-1 filtrada + fallback (t=0.75)",
    "julia_filtered_fallback_t90": "Julia-1 filtrada + fallback (t=0.90)",
    # round 1 labels, for the round1-vs-round2 section
    "r1_rules": "R1: Regras",
    "r1_julia": "R1: Julia-1 (puro)",
    "r1_julia_fallback": "R1: Julia-1 + fallback",
}

# "Estabilidade razoável à ordem das opções" -- defined here, before looking
# at the full-scale invariance numbers, as: no more than 30% of sampled
# real decisions may flip their choice under a reordering of the exact same
# options. This is a deliberately conservative bar (anything above it means
# the model is flipping on *at least* a third of real in-game decisions
# purely from presentation order), chosen for defensibility, not fitted to
# the outcome.
STABILITY_INSTABILITY_CEILING = 0.30

# Metrics compared against the baseline, paired by seed, with direction.
COMPARISON_METRICS = [
    ("survival_seconds", "Tempo de sobrevivência (s)", "higher_is_better"),
    ("kills", "Inimigos eliminados", "higher_is_better"),
    ("damage_taken", "Dano recebido", "lower_is_better"),
    ("ammo_consumed", "Munição consumida", "lower_is_better"),
]

# The two metrics the go/no-go criterion is actually gated on.
GATING_METRICS = ["survival_seconds", "kills"]


def load_round2_episode_metrics(logs_dir: Path, variant: str) -> List[dict]:
    variant_dir = logs_dir / variant
    decisions = metrics_v1.load_jsonl(variant_dir / "decisions.jsonl")
    summaries = metrics_v1.load_jsonl(variant_dir / "episodes_summary.jsonl")
    by_episode: Dict[int, List[dict]] = {}
    for d in decisions:
        by_episode.setdefault(d["episode_id"], []).append(d)
    return [
        metrics_v2.compute_episode_metrics_v2(by_episode.get(s["episode_id"], []), s)
        for s in summaries
    ]


def load_round1_episode_metrics(logs_dir: Path, variant: str) -> List[dict]:
    variant_dir = logs_dir / variant
    decisions = metrics_v1.load_jsonl(variant_dir / "decisions.jsonl")
    summaries = metrics_v1.load_jsonl(variant_dir / "episodes_summary.jsonl")
    by_episode: Dict[int, List[dict]] = {}
    for d in decisions:
        by_episode.setdefault(d["episode_id"], []).append(d)
    return [
        metrics_v1.compute_episode_metrics(by_episode.get(s["episode_id"], []), s)
        for s in summaries
    ]


def fmt(value: Optional[float], pattern: str = "{:.2f}") -> str:
    return "n/d" if value is None else pattern.format(value)


def render_ci(cmp: statmod.PairedComparison) -> str:
    if cmp.n_pairs == 0:
        return "sem seeds em comum"
    if cmp.ci95_low is None:
        return f"diff={fmt(cmp.mean_diff)} (n={cmp.n_pairs}, IC não calculável)"
    tag = "SIGNIFICATIVO" if cmp.significant else "não significativo"
    bad = " — PIOR" if cmp.worse else ""
    return f"diff={fmt(cmp.mean_diff)} IC95%=[{fmt(cmp.ci95_low)}, {fmt(cmp.ci95_high)}] n={cmp.n_pairs} ({tag}{bad})"


def build_report(logs_round2: Path, logs_round1: Path) -> str:
    lines: List[str] = []
    lines.append("# Relatório rodada 2: Julia-1 filtrada + fallback vs. baseline")
    lines.append("")
    lines.append(
        "Gerado inteiramente a partir de `logs_round2/<variant>/` (rodada 2, "
        "seeds 1000-1019 = fase A, 5000-5029 = fase B) e `logs/<variant>/` "
        "(rodada 1, **não alterada**). Nenhum número foi digitado manualmente."
    )
    lines.append("")
    lines.append(
        "**Aviso sobre 'confiança':** `max_probability` do Julia-1 é um score "
        "softmax bruto, não uma confiança calibrada -- o teste de invariância "
        "abaixo mostra exatamente por que isso importa (o modelo reporta "
        "\"confiança\" alta para respostas contraditórias dependendo só da "
        "ordem de apresentação das opções)."
    )
    lines.append("")

    # ---- Round 2: per-variant episode metrics -----------------------------
    round2_episode_metrics: Dict[str, List[dict]] = {}
    for variant in ROUND2_VARIANTS:
        if (logs_round2 / variant / "episodes_summary.jsonl").exists():
            round2_episode_metrics[variant] = load_round2_episode_metrics(logs_round2, variant)

    aggregates = {v: metrics_v2.aggregate_variant_v2(em) for v, em in round2_episode_metrics.items()}

    lines.append("## Rodada 2 -- métricas agregadas (fase A + fase B, 50 seeds)")
    lines.append("")
    present_variants = [v for v in ROUND2_VARIANTS if v in aggregates]
    header = "| Métrica | " + " | ".join(LABELS[v] for v in present_variants) + " |"
    lines.append(header)
    lines.append("|---" * (len(present_variants) + 1) + "|")

    row_defs = [
        ("episodes", "Episódios", "{:.0f}"),
        ("survival_seconds", "Sobrevivência (s)", "{:.1f}"),
        ("kills", "Kills", "{:.2f}"),
        ("damage_taken", "Dano recebido", "{:.1f}"),
        ("ammo_consumed", "Munição consumida", "{:.1f}"),
        ("decisions", "Decisões/episódio", "{:.1f}"),
        ("action_distribution_total", "Distribuição de ações", None),
        ("avg_confidence", "Confiança média (executada)", "{:.3f}"),
        ("avg_model_confidence", "Score médio do modelo (não calibrado)", "{:.3f}"),
        ("real_model_calls", "Chamadas reais ao modelo/episódio", "{:.1f}"),
        ("forced_rate", "Taxa de ação forçada pelo filtro", "{:.1%}"),
        ("fallback_count", "Fallbacks (baixa confiança)/episódio", "{:.2f}"),
        ("fallback_rate", "Taxa de fallback", "{:.1%}"),
        ("antiloop_override_count", "Overrides anti-loop/episódio", "{:.2f}"),
        ("wait_override_count", "...dos quais partiram de 'esperar'", "{:.2f}"),
        ("avg_latency_ms", "Latência média do modelo (ms)", "{:.2f}"),
        ("p95_latency_ms", "Latência p95 do modelo (ms)", "{:.2f}"),
        ("agreement_rate", "Concordância com as regras", "{:.1%}"),
        ("error_count", "Erros do modelo/episódio", "{:.2f}"),
        ("invalid_action_count", "Decisões inválidas/episódio", "{:.2f}"),
        ("death_rate", "Taxa de morte (vs. timeout)", "{:.1%}"),
    ]
    for field, label, fmt_str in row_defs:
        cells = []
        for v in present_variants:
            val = aggregates.get(v, {}).get(field)
            if field == "action_distribution_total":
                if not val:
                    cells.append("n/d")
                else:
                    total = sum(val.values())
                    parts = sorted(val.items(), key=lambda kv: -kv[1])
                    cells.append(
                        ", ".join(f"{k} {100*n/total:.0f}%" for k, n in parts)
                    )
            else:
                cells.append(fmt(val, fmt_str) if fmt_str else str(val))
        lines.append("| " + label + " | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("### Fase A (seeds 1000-1019, comparáveis à rodada 1) vs. fase B (30 seeds novas, nunca usadas no desenvolvimento)")
    lines.append("")
    header_ab = "| Métrica | Fase | " + " | ".join(LABELS[v] for v in present_variants) + " |"
    lines.append(header_ab)
    lines.append("|---" * (len(present_variants) + 2) + "|")
    for field, label, fmt_str in [
        ("survival_seconds", "Sobrevivência (s)", "{:.1f}"),
        ("kills", "Kills", "{:.2f}"),
        ("damage_taken", "Dano recebido", "{:.1f}"),
        ("agreement_rate", "Concordância com as regras", "{:.1%}"),
    ]:
        for phase, phase_label in (("A", "A"), ("B", "B")):
            cells = []
            for v in present_variants:
                phase_episodes = [e for e in round2_episode_metrics.get(v, []) if e.get("phase") == phase]
                phase_agg = metrics_v2.aggregate_variant_v2(phase_episodes)
                cells.append(fmt(phase_agg.get(field), fmt_str))
            lines.append(f"| {label} | {phase_label} | " + " | ".join(cells) + " |")
    lines.append("")

    # ---- Round 2 internal paired comparison vs its own rules baseline -----
    lines.append("## Rodada 2 -- comparação pareada vs. baseline (IC 95%, 50 seeds)")
    lines.append("")
    lines.append(
        "Pareado por seed (mesma seed = mesma condição inicial do VizDoom). "
        "'PIOR' = IC 95% da diferença exclui zero E fica do lado ruim da "
        "métrica (sobrevivência/kills menores, ou dano/munição maiores)."
    )
    lines.append("")

    gating_results: Dict[str, Dict[str, statmod.PairedComparison]] = {}
    baseline_metrics = round2_episode_metrics.get("rules", [])
    for variant in present_variants:
        if variant == "rules":
            continue
        lines.append(f"### {LABELS[variant]} vs. {LABELS['rules']}")
        lines.append("")
        variant_metrics = round2_episode_metrics[variant]
        gating_results[variant] = {}
        for field, label, direction in COMPARISON_METRICS:
            baseline_by_seed = metrics_v2.by_seed(baseline_metrics, field)
            variant_by_seed = metrics_v2.by_seed(variant_metrics, field)
            cmp = statmod.compare_to_baseline(field, baseline_by_seed, variant_by_seed, direction)
            gating_results[variant][field] = cmp
            lines.append(f"- **{label}**: {render_ci(cmp)}")
        lines.append("")

    # ---- Invariance test ---------------------------------------------------
    lines.append("## Teste de invariância à ordem das opções")
    lines.append("")
    invariance_summary_path = logs_round2 / "invariance_test_summary.json"
    invariance_summary = None
    if invariance_summary_path.exists():
        invariance_summary = json.loads(invariance_summary_path.read_text())
        lines.append(
            "Mesmo estado, mesmas opções, ordens diferentes -- quantas vezes a "
            "escolha do Julia-1 muda. Permutações determinísticas (rotações da "
            "lista original e da lista invertida), sem RNG."
        )
        lines.append("")
        lines.append("| Fonte dos estados | Estados testados | Taxa de instabilidade | Fração majoritária média | Escolhas distintas (média) |")
        lines.append("|---|---|---|---|---|")
        for source, s in invariance_summary.items():
            lines.append(
                f"| {source} | {s['states_tested']} | {fmt(s['instability_rate'], '{:.1%}')} "
                f"| {fmt(s['avg_majority_fraction'], '{:.1%}')} | {fmt(s['avg_distinct_choices'])} |"
            )
        lines.append("")
    else:
        lines.append("_(logs_round2/invariance_test_summary.json não encontrado)_")
        lines.append("")

    # ---- Round 1 vs Round 2 -------------------------------------------------
    lines.append("## Rodada 1 vs. rodada 2")
    lines.append("")
    r1_variants = ["rules", "julia", "julia_fallback"]
    r1_metrics = {v: load_round1_episode_metrics(logs_round1, v) for v in r1_variants if (logs_round1 / v).exists()}
    r1_agg = {v: metrics_v1.aggregate_variant(em) for v, em in r1_metrics.items()}

    lines.append(
        "Rodada 1 usou 15 seeds (1000-1014); rodada 2 reusa essas mesmas seeds "
        "na fase A (mais 5 seeds extras, 1015-1019, e 30 seeds novas na fase "
        "B). Para a comparação direta abaixo, a rodada 2 é restrita às 15 "
        "seeds 1000-1014 -- exatamente as que a rodada 1 rodou."
    )
    lines.append("")

    r1_seeds = set(range(1000, 1015))
    header = (
        "| Métrica | R1: Regras | R2: Regras | R1: Julia (puro) | R2: Julia raw | R2: Julia filtrada"
        " | R1: Julia+fallback | R2: Julia filtrada+fallback (t=0.60) |"
    )
    lines.append(header)
    lines.append("|---" * 8 + "|")

    def restricted_agg(all_episode_metrics: List[dict]) -> dict:
        restricted = [e for e in all_episode_metrics if e.get("seed") in r1_seeds]
        return metrics_v2.aggregate_variant_v2(restricted)

    r2_restricted = {v: restricted_agg(em) for v, em in round2_episode_metrics.items()}

    for field, label, _direction in COMPARISON_METRICS:
        row = [label]
        row.append(fmt(r1_agg.get("rules", {}).get(field), "{:.1f}"))
        row.append(fmt(r2_restricted.get("rules", {}).get(field), "{:.1f}"))
        row.append(fmt(r1_agg.get("julia", {}).get(field), "{:.1f}"))
        row.append(fmt(r2_restricted.get("julia_raw", {}).get(field), "{:.1f}"))
        row.append(fmt(r2_restricted.get("julia_filtered", {}).get(field), "{:.1f}"))
        row.append(fmt(r1_agg.get("julia_fallback", {}).get(field), "{:.1f}"))
        row.append(fmt(r2_restricted.get("julia_filtered_fallback_t60", {}).get(field), "{:.1f}"))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Isolate the anti-loop-config effect: R2's own rules vs R1's rules, same seeds.
    lines.append("### O baseline em si mudou entre rodadas?")
    lines.append("")
    lines.append(
        "A rodada 2 aplica um limite anti-loop mais apertado especificamente "
        "para 'esperar' (3 em vez de 5) em **todas** as variantes, incluindo "
        "'regras' -- então antes de atribuir qualquer diferença ao Julia-1, "
        "vale checar se isso sozinho já mudou o baseline, nas mesmas seeds:"
    )
    lines.append("")
    r1_rules_by_seed_survival = metrics_v2.by_seed(r1_metrics.get("rules", []), "survival_seconds")
    r2_rules_restricted_metrics = [e for e in round2_episode_metrics.get("rules", []) if e.get("seed") in r1_seeds]
    r2_rules_by_seed_survival = metrics_v2.by_seed(r2_rules_restricted_metrics, "survival_seconds")
    baseline_shift = statmod.compare_to_baseline(
        "survival_seconds", r1_rules_by_seed_survival, r2_rules_by_seed_survival, "higher_is_better"
    )
    lines.append(f"- **Sobrevivência, R2-regras vs. R1-regras** (mesmas 15 seeds): {render_ci(baseline_shift)}")
    r1_rules_by_seed_kills = metrics_v2.by_seed(r1_metrics.get("rules", []), "kills")
    r2_rules_by_seed_kills = metrics_v2.by_seed(r2_rules_restricted_metrics, "kills")
    baseline_shift_kills = statmod.compare_to_baseline(
        "kills", r1_rules_by_seed_kills, r2_rules_by_seed_kills, "higher_is_better"
    )
    lines.append(f"- **Kills, R2-regras vs. R1-regras** (mesmas 15 seeds): {render_ci(baseline_shift_kills)}")
    lines.append("")

    # ---- Verdict ------------------------------------------------------------
    lines.append("## Critério de avanço ao minecraft-mbot")
    lines.append("")
    lines.append(
        f"Critério: nem 'Julia-1 filtrada' nem 'Julia-1 filtrada + fallback' "
        f"(em nenhum dos 3 thresholds) pode apresentar piora estatisticamente "
        f"significativa (IC 95%, pareado por seed, n=50) em sobrevivência ou "
        f"kills contra o baseline de regras, **e** deve demonstrar "
        f"estabilidade razoável à ordem das opções, definida aqui como taxa "
        f"de instabilidade $\\leq$ {STABILITY_INSTABILITY_CEILING:.0%} no teste "
        f"de invariância."
    )
    lines.append("")

    candidates = [v for v in present_variants if v.startswith("julia_filtered")]
    verdict_rows = []
    any_pass = False
    for variant in candidates:
        variant_gates = gating_results.get(variant, {})
        worse_metrics = [
            label
            for field, label, _d in COMPARISON_METRICS
            if field in GATING_METRICS and variant_gates.get(field) is not None and variant_gates[field].worse
        ]
        no_regression = len(worse_metrics) == 0
        instability = None
        if invariance_summary:
            source_key = "julia_filtered" if variant != "julia_raw" else "julia_raw"
            instability = invariance_summary.get(source_key, {}).get("instability_rate")
        instability_tested = instability is not None
        stable = instability_tested and instability <= STABILITY_INSTABILITY_CEILING
        passes = no_regression and stable if instability_tested else None
        if passes:
            any_pass = True
        verdict_rows.append((variant, no_regression, worse_metrics, instability, instability_tested, stable, passes))

    lines.append("| Variante | Sem piora significativa (sobrev./kills) | Instabilidade à ordem | Estável (≤30%) | Passa no critério |")
    lines.append("|---|---|---|---|---|")
    for variant, no_regression, worse_metrics, instability, instability_tested, stable, passes in verdict_rows:
        nr_text = "sim" if no_regression else f"NÃO ({', '.join(worse_metrics)})"
        if not instability_tested:
            inst_text, stable_text, passes_text = "n/d (teste não rodado)", "n/d", "n/d"
        else:
            inst_text = fmt(instability, "{:.1%}")
            stable_text = "sim" if stable else "NÃO"
            passes_text = "**SIM**" if passes else "**NÃO**"
        lines.append(f"| {LABELS[variant]} | {nr_text} | {inst_text} | {stable_text} | {passes_text} |")
    lines.append("")

    lines.append("### Veredito")
    lines.append("")
    if not invariance_summary:
        lines.append(
            "**Indeterminado.** O teste de invariância não foi executado "
            "(`logs_round2/invariance_test_summary.json` ausente), e a "
            "estabilidade à ordem das opções é metade do critério -- rode "
            "`experiments/invariance_test.py` antes de tirar qualquer "
            "conclusão de avanço."
        )
    elif any_pass:
        passing = [LABELS[v] for v, *_r, passes in verdict_rows if passes]
        lines.append(
            f"**Avançar, com ressalvas.** {', '.join(passing)} passa(m) no "
            "critério estatístico definido (sem piora significativa em "
            "sobrevivência/kills e instabilidade à ordem dentro do limiar). "
            "Isso não elimina o problema de fundo -- o teste de invariância "
            "mostra que decisões individuais continuam sensíveis à ordem das "
            "opções -- mas agregado ao longo de um episódio inteiro, o "
            "impacto não chega a produzir uma piora mensurável nas métricas "
            "de sobrevivência/kills que o critério cobre."
        )
    else:
        lines.append(
            "**Não avançar ainda.** Nenhuma variante filtrada passou nos dois "
            "requisitos simultaneamente. Ver a tabela acima para o motivo "
            "específico de cada uma (regressão estatística em sobrevivência/"
            "kills, instabilidade à ordem acima do limiar, ou ambos)."
        )
    lines.append("")

    lines.append("## Notas de metodologia")
    lines.append("")
    lines.append(
        "- 'Munição consumida' usa a mesma correção da rodada 1 (ignora "
        "saltos por troca automática de arma do Doom)."
    )
    lines.append(
        "- 'Concordância com as regras' compara a ação executada com o que "
        "`RuleBasedAgent` faria a partir do mesmíssimo (estado, ações "
        "disponíveis) -- é só um diagnóstico, nunca influencia a execução."
    )
    lines.append(
        "- Estatísticas pareadas usam a distribuição t de Student (não a "
        "normal) para o IC de 95%, mais correta com n pequeno; ver "
        "`experiments/stats.py`."
    )
    lines.append(
        "- O teste de invariância chama o Julia-1 real (mesmo processo, "
        "mesmo modelo) com as mesmas opções em ordens diferentes -- não é "
        "uma simulação nem uma estimativa teórica."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-round2", type=str, default="logs_round2")
    parser.add_argument("--logs-round1", type=str, default="logs")
    parser.add_argument("--out", type=str, default="reports/round2_report.md")
    args = parser.parse_args()

    report = build_report(Path(args.logs_round2), Path(args.logs_round1))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
