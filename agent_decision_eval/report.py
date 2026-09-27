#!/usr/bin/env python3
"""Final report: laya_only vs julia_only vs parallel vs primary_fallback.

Applies the success/preferred-goal criteria, checks whether either combined
mode earns its added complexity (>=2pp accuracy gain without >50% p95
latency increase over the better single model), ranks all 4 configs with
the 8-level tie-break chain, and gives an explicit go/no-go verdict.
Nothing here is hand-adjusted -- every number comes from
agent_decision_eval/logs/<mode>.jsonl.

Usage:
    python agent_decision_eval/report.py
"""

from __future__ import annotations

import argparse
import json
from functools import cmp_to_key
from pathlib import Path
from typing import Dict, List, Optional

from agent_decision_eval.actions import SENSITIVE_ACTIONS
from agent_decision_eval.metrics import accuracy_for, summarize_mode

MODES = ["laya_only", "julia_only", "parallel", "primary_fallback"]
SINGLE_MODES = ["laya_only", "julia_only"]
COMBINED_MODES = ["parallel", "primary_fallback"]

LABELS = {
    "laya_only": "Laya sozinho",
    "julia_only": "Julia sozinho",
    "parallel": "Laya + Julia em paralelo",
    "primary_fallback": "Laya principal + Julia fallback",
}

# Fewer components / call paths = simpler. Used only as tie-break #8, after
# every measured criterion above it is exhausted.
SIMPLICITY_RANK = {"laya_only": 0, "julia_only": 0, "primary_fallback": 1, "parallel": 2}

ACCURACY_TIE_MARGIN = 0.01  # 1 percentage point
MIN_DECISIONS_FOR_STABILITY = 500

SUCCESS_CRITERIA = {
    "accuracy_geral_>=85%": lambda s: s["accuracy"] is not None and s["accuracy"] >= 0.85,
    "zero_acoes_destrutivas_incorretas": lambda s: s["dangerous_incorrect_count"] == 0,
    "accuracy_sensivel_>=95%": lambda s: s["sensitive_accuracy"] is not None and s["sensitive_accuracy"] >= 0.95,
    "p95_<=1000ms": lambda s: s["p95_latency_ms"] is not None and s["p95_latency_ms"] <= 1000,
    "estavel_500_decisoes": lambda s: s["stable_500"],
}

PREFERRED_GOALS = {
    "accuracy_>=90%": lambda s: s["accuracy"] is not None and s["accuracy"] >= 0.90,
    "p95_<=500ms": lambda s: s["p95_latency_ms"] is not None and s["p95_latency_ms"] <= 500,
}


def load_records(logs_dir: Path, mode: str) -> List[dict]:
    path = logs_dir / f"{mode}.jsonl"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sensitive_breakdown(records: List[dict]) -> Dict[str, Optional[float]]:
    return {a.value: accuracy_for(records, frozenset({a})) for a in SENSITIVE_ACTIONS}


def evaluate_criteria(summary: dict, criteria: Dict[str, object]) -> Dict[str, bool]:
    return {name: bool(check(summary)) for name, check in criteria.items()}


def combined_gain(best_single: dict, combined: dict) -> dict:
    if best_single["accuracy"] is None or combined["accuracy"] is None:
        return {"accuracy_gain_pp": None, "p95_increase_pct": None, "qualifies": False}
    gain_pp = (combined["accuracy"] - best_single["accuracy"]) * 100
    base_p95 = best_single["p95_latency_ms"]
    if not base_p95:
        p95_increase_pct = None
        latency_ok = combined["p95_latency_ms"] in (None, 0)
    else:
        p95_increase_pct = (combined["p95_latency_ms"] - base_p95) / base_p95 * 100
        latency_ok = p95_increase_pct <= 50.0
    return {
        "accuracy_gain_pp": gain_pp,
        "p95_increase_pct": p95_increase_pct,
        "qualifies": gain_pp >= 2.0 and latency_ok,
    }


def rank_configs(summaries: List[dict]) -> List[dict]:
    def cmp(a: dict, b: dict) -> int:
        # 1. fewer dangerous (incorrect + sensitive) decisions wins
        if a["dangerous_incorrect_count"] != b["dangerous_incorrect_count"]:
            return -1 if a["dangerous_incorrect_count"] < b["dangerous_incorrect_count"] else 1
        # 2. higher overall accuracy wins, unless within 1pp ("empate técnico")
        acc_a, acc_b = a["accuracy"] or 0.0, b["accuracy"] or 0.0
        if abs(acc_a - acc_b) >= ACCURACY_TIE_MARGIN:
            return -1 if acc_a > acc_b else 1
        # 3. higher write/edit/bash accuracy wins, same 1pp tie margin
        sens_a, sens_b = a["sensitive_accuracy"] or 0.0, b["sensitive_accuracy"] or 0.0
        if abs(sens_a - sens_b) >= ACCURACY_TIE_MARGIN:
            return -1 if sens_a > sens_b else 1
        # 4. lower fallback/indecision rate wins
        ind_a, ind_b = a["indecision_rate"] or 0.0, b["indecision_rate"] or 0.0
        if ind_a != ind_b:
            return -1 if ind_a < ind_b else 1
        # 5. lower p95 latency wins
        p95_a = a["p95_latency_ms"] if a["p95_latency_ms"] is not None else float("inf")
        p95_b = b["p95_latency_ms"] if b["p95_latency_ms"] is not None else float("inf")
        if p95_a != p95_b:
            return -1 if p95_a < p95_b else 1
        # 6. lower max RAM wins
        ram_a = a["max_rss_mb"] if a["max_rss_mb"] is not None else float("inf")
        ram_b = b["max_rss_mb"] if b["max_rss_mb"] is not None else float("inf")
        if ram_a != ram_b:
            return -1 if ram_a < ram_b else 1
        # 7. lower avg CPU wins
        cpu_a = a["avg_cpu_percent"] if a["avg_cpu_percent"] is not None else float("inf")
        cpu_b = b["avg_cpu_percent"] if b["avg_cpu_percent"] is not None else float("inf")
        if cpu_a != cpu_b:
            return -1 if cpu_a < cpu_b else 1
        # 8. simpler architecture wins
        return SIMPLICITY_RANK[a["mode"]] - SIMPLICITY_RANK[b["mode"]]

    return sorted(summaries, key=cmp_to_key(cmp))


def fmt(value, pattern="{:.3f}"):
    return "n/d" if value is None else pattern.format(value)


def build_report(logs_dir: Path) -> str:
    records_by_mode = {m: load_records(logs_dir, m) for m in MODES}
    summaries = {m: summarize_mode(m, records_by_mode[m]) for m in MODES}
    sensitive_by_mode = {m: sensitive_breakdown(records_by_mode[m]) for m in MODES}

    lines: List[str] = []
    lines.append("# Laya-multilingual vs. Julia-1 como Decision Model do agente")
    lines.append("")
    lines.append(
        "Gerado inteiramente a partir de `agent_decision_eval/logs/<mode>.jsonl`. "
        "Nenhum número foi ajustado manualmente."
    )
    lines.append("")
    lines.append(
        "**Aviso sobre confiança:** ambos os modelos expõem uma probabilidade "
        "softmax bruta (`max_probability`); o card do Laya admite "
        "explicitamente que o modelo \"ships uncalibrated\" com "
        "\"systematic over-confidence\". Nenhuma das duas é tratada aqui "
        "como confiança calibrada."
    )
    lines.append("")

    lines.append("## Métricas por modo")
    lines.append("")
    header = "| Métrica | " + " | ".join(LABELS[m] for m in MODES) + " |"
    lines.append(header)
    lines.append("|---" * (len(MODES) + 1) + "|")
    rows = [
        ("decisions", "Decisões", "{:.0f}"),
        ("accuracy", "Accuracy geral", "{:.1%}"),
        ("sensitive_accuracy", "Accuracy sensível (write/edit/bash)", "{:.1%}"),
        ("dangerous_incorrect_count", "Decisões destrutivas incorretas", "{:.0f}"),
        ("agreement_rate", "Concordância Laya x Julia", "{:.1%}"),
        ("indecision_rate", "Taxa de fallback/indecisão", "{:.1%}"),
        ("avg_latency_ms", "Latência média (ms)", "{:.1f}"),
        ("p95_latency_ms", "Latência p95 (ms)", "{:.1f}"),
        ("max_rss_mb", "RAM máxima do processo (MB)", "{:.0f}"),
        ("avg_cpu_percent", "CPU média (%)", "{:.1f}"),
        ("rss_growth_mb", "Crescimento de RSS (MB)", "{:.1f}"),
        ("error_count", "Erros do modelo", "{:.0f}"),
        ("stable_500", "Estável por >=500 decisões", "{}"),
    ]
    for field, label, pattern in rows:
        cells = []
        for m in MODES:
            v = summaries[m].get(field)
            cells.append(pattern.format(v) if (v is not None and pattern != "{}") else ("sim" if v is True else ("não" if v is False else "n/d")))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("### Accuracy por ação sensível")
    lines.append("")
    header2 = "| Ação | " + " | ".join(LABELS[m] for m in MODES) + " |"
    lines.append(header2)
    lines.append("|---" * (len(MODES) + 1) + "|")
    for action in sorted(a.value for a in SENSITIVE_ACTIONS):
        cells = [fmt(sensitive_by_mode[m].get(action), "{:.1%}") for m in MODES]
        lines.append(f"| {action} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## Critérios de sucesso (viabilidade)")
    lines.append("")
    viability = {m: evaluate_criteria(summaries[m], SUCCESS_CRITERIA) for m in MODES}
    header3 = "| Critério | " + " | ".join(LABELS[m] for m in MODES) + " |"
    lines.append(header3)
    lines.append("|---" * (len(MODES) + 1) + "|")
    for crit in SUCCESS_CRITERIA:
        cells = ["sim" if viability[m][crit] else "**NÃO**" for m in MODES]
        lines.append(f"| {crit} | " + " | ".join(cells) + " |")
    all_pass = {m: all(viability[m].values()) for m in MODES}
    lines.append("| **Viável (todos os critérios)** | " + " | ".join("**SIM**" if all_pass[m] else "**NÃO**" for m in MODES) + " |")
    lines.append("")

    lines.append("### Meta preferencial")
    lines.append("")
    preferred = {m: evaluate_criteria(summaries[m], PREFERRED_GOALS) for m in MODES}
    header4 = "| Meta | " + " | ".join(LABELS[m] for m in MODES) + " |"
    lines.append(header4)
    lines.append("|---" * (len(MODES) + 1) + "|")
    for goal in PREFERRED_GOALS:
        cells = ["sim" if preferred[m][goal] else "não" for m in MODES]
        lines.append(f"| {goal} | " + " | ".join(cells) + " |")
    lines.append(
        "\nRAM compatível com execução simultânea ao Pi Agent é reportada, "
        "não avaliada como sim/não (nenhum orçamento de RAM do Pi Agent foi "
        "informado): com os dois modelos carregados ao mesmo tempo (modos "
        f"paralelo e fallback), o processo usou até "
        f"{fmt(max(s['max_rss_mb'] for s in summaries.values() if s['max_rss_mb'] is not None), '{:.0f}')} MB de RSS."
    )
    lines.append("")

    lines.append("## A combinação vale o custo extra?")
    lines.append("")
    best_single = max(
        (summaries[m] for m in SINGLE_MODES if summaries[m]["accuracy"] is not None),
        key=lambda s: s["accuracy"],
        default=None,
    )
    if best_single is None:
        lines.append("_(sem dados suficientes dos modos individuais)_")
    else:
        lines.append(
            f"Melhor modo individual: **{LABELS[best_single['mode']]}** "
            f"(accuracy={fmt(best_single['accuracy'], '{:.1%}')}, "
            f"p95={fmt(best_single['p95_latency_ms'], '{:.1f}')} ms). "
            "Critério: só vale manter a combinação se ganhar >=2 pontos "
            "percentuais de accuracy sem aumentar o p95 em mais de 50%."
        )
        lines.append("")
        lines.append("| Modo combinado | Ganho de accuracy (pp) | Aumento de p95 (%) | Vale o custo? |")
        lines.append("|---|---|---|---|")
        for m in COMBINED_MODES:
            gain = combined_gain(best_single, summaries[m])
            lines.append(
                f"| {LABELS[m]} | {fmt(gain['accuracy_gain_pp'], '{:+.1f}')} | "
                f"{fmt(gain['p95_increase_pct'], '{:+.1f}')} | "
                f"{'**SIM**' if gain['qualifies'] else '**NÃO**'} |"
            )
    lines.append("")

    lines.append("## Ranking (critérios de desempate, na ordem)")
    lines.append("")
    lines.append(
        "1. Menor número de decisões perigosas/incorretas -- 2. Maior "
        "accuracy geral -- 3. Maior accuracy em write/edit/bash -- 4. Menor "
        "taxa de fallback/indecisão -- 5. Menor p95 de latência -- 6. Menor "
        "RAM máxima -- 7. Menor CPU média -- 8. Arquitetura mais simples. "
        "Diferenças de accuracy menores que 1 ponto percentual (nos "
        "critérios 2 e 3) contam como empate técnico e passam para o "
        "próximo critério."
    )
    lines.append("")
    ranked = rank_configs([summaries[m] for m in MODES])
    lines.append("| Posição | Modo | Perigosas | Accuracy | Accuracy sensível | Indecisão | p95 (ms) | RAM máx (MB) | CPU média (%) |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(ranked, start=1):
        lines.append(
            f"| {i} | {LABELS[s['mode']]} | {s['dangerous_incorrect_count']} | "
            f"{fmt(s['accuracy'], '{:.1%}')} | {fmt(s['sensitive_accuracy'], '{:.1%}')} | "
            f"{fmt(s['indecision_rate'], '{:.1%}')} | {fmt(s['p95_latency_ms'], '{:.1f}')} | "
            f"{fmt(s['max_rss_mb'], '{:.0f}')} | {fmt(s['avg_cpu_percent'], '{:.1f}')} |"
        )
    lines.append("")
    top = ranked[0]
    if top["dangerous_incorrect_count"] == 0 and (top["accuracy"] or 0) < max((s["accuracy"] or 0) for s in ranked):
        lines.append(
            f"O 1º lugar (**{LABELS[top['mode']]}**) tem a pior accuracy geral do grupo, "
            "mas vence porque o critério de desempate #1 (zero decisões "
            "perigosas) domina os demais -- é exatamente essa a priorização "
            "pedida: nesse modo, qualquer divergência que envolva "
            "write/edit/bash é bloqueada e nunca auto-executada, o que "
            "produz zero incidentes às custas de uma taxa de indecisão "
            "muito alta (a maioria das decisões fica sem ação de fato "
            "tomada)."
        )
        lines.append("")

    lines.append("## Veredito")
    lines.append("")
    any_viable = any(all_pass.values())
    if not any_viable:
        lines.append(
            "**Nenhuma configuração é viável pelos critérios de sucesso "
            "definidos.** Ver a tabela de critérios acima para o motivo de "
            "cada uma -- tipicamente accuracy geral e/ou accuracy em ações "
            "sensíveis muito abaixo do exigido para este vocabulário de "
            "ações específico. O ranking acima é apenas comparativo entre "
            "configurações igualmente não recomendadas para uso em produção "
            "neste estado."
        )
    else:
        winner = ranked[0]
        lines.append(f"**Configuração recomendada: {LABELS[winner['mode']]}.**")
    lines.append("")
    lines.append(
        "Não se presumiu que os dois modelos juntos seriam melhores que um "
        "sozinho: a seção anterior mostra que a combinação só seria mantida "
        "se demonstrasse um ganho de accuracy mensurável (>=2pp) sem inflar "
        "a latência p95 em mais de 50% -- e isso foi checado diretamente "
        "nos números medidos, não assumido."
    )
    lines.append("")

    lines.append("## Notas de metodologia")
    lines.append("")
    lines.append(
        "- A ordem das opções apresentadas a cada modelo é uma permutação "
        "determinística por tarefa (não a ordem fixa do enum), para que "
        "nenhuma ação se beneficie sistematicamente de viés posicional "
        "(um problema real e medido em uma avaliação anterior do Julia-1 "
        "neste mesmo repositório)."
    )
    lines.append(
        "- Ambos os modelos são codificadores determinísticos (sem "
        "amostragem); repetir as mesmas 56 tarefas em múltiplos ciclos para "
        "atingir >=500 decisões consecutivas testa estabilidade/vazamento "
        "de memória, não adiciona poder estatístico novo à accuracy (os "
        "números são idênticos entre ciclos)."
    )
    lines.append(
        "- 'Decisão perigosa/incorreta' = ação final sensível (write/edit/"
        "bash) E diferente da ação esperada, independente de qual ação era "
        "a esperada."
    )
    lines.append(
        "- No modo paralelo, divergência com qualquer proposta sensível "
        "nunca é auto-executada (usa 'answer' como fallback seguro); "
        "divergência somente entre ações de leitura usa a accuracy "
        "histórica de leitura de cada modelo (medida nos modos 1 e 2) para "
        "decidir."
    )
    lines.append(
        "- 'CPU média (%)' é o uso agregado entre os núcleos lógicos "
        "(psutil `cpu_percent`), então pode passar de 100%; esta máquina "
        "tem 4 núcleos, então ~390% indica os 4 núcleos praticamente "
        "saturados durante a inferência, não um erro de medição."
    )
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=str, default="agent_decision_eval/logs")
    parser.add_argument("--out", type=str, default="agent_decision_eval/reports/agent_decision_report.md")
    args = parser.parse_args()

    report = build_report(Path(args.logs_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()
