# Como reproduzir a rodada 2

Pré-requisito: siga `docs/REPRODUCE.md` primeiro (venv, `pip install -r requirements.txt`,
`python scripts/setup_julia_model.py`). A rodada 2 usa o mesmo modelo Julia-1 já baixado.

## O que muda da rodada 1

- **4 agentes** em vez de 3: `rules`, `julia_raw` (era só "julia" na rodada 1),
  `julia_filtered` (novo: filtro determinístico de ações antes de chamar o
  Julia-1) e `julia_filtered_fallback` (novo: filtro + fallback por
  confiança, testado em 3 thresholds: 0.60, 0.75, 0.90).
- **Anti-loop com limite específico para "esperar"** (3 repetições em vez de
  5), já que a rodada 1 mostrou que o Julia-1 usa "esperar" como padrão bem
  mais que o baseline.
- **Teste de invariância à ordem das opções**: mesmo estado, mesmas opções,
  ordens diferentes -- quantas vezes a escolha muda.
- **Concordância com as regras**: toda decisão do Julia é logada junto com o
  que `RuleBasedAgent` faria a partir do mesmo estado (só para comparação,
  nunca afeta a execução).
- **Comparação estatística pareada (IC 95%)** contra o baseline, por seed.

A rodada 1 (`run_experiment.py`, `report.py`, `logs/`) não foi tocada -- os
resultados e o relatório originais continuam reproduzíveis exatamente como
documentado em `docs/REPRODUCE.md`.

## 1. Rodar os 6 agentes/thresholds

Script único que roda tudo em sequência (fase A: seeds 1000-1019; fase B: 30
seeds novas, 5000-5029):

```bash
bash scripts/run_round2_all.sh
```

Ou variante por variante:

```bash
source .venv/bin/activate
export PYTHONPATH=.

python experiments/run_experiment_v2.py --variant rules
python experiments/run_experiment_v2.py --variant julia_raw
python experiments/run_experiment_v2.py --variant julia_filtered
python experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.60
python experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.75
python experiments/run_experiment_v2.py --variant julia_filtered_fallback --confidence-threshold 0.90
```

Saída em `logs_round2/<variant>/{decisions.jsonl,episodes_summary.jsonl,run_meta.json}`
(`<variant>` inclui o threshold no nome para os 3 fallbacks: `julia_filtered_fallback_t60` etc).

Tempo esperado: ~30-40 min no total (50 episódios × 6 variantes; `rules` é
quase instantâneo, cada variante com Julia-1 chama o modelo real a cada
decisão).

## 2. Teste de invariância à ordem das opções

Depois que `julia_raw` e `julia_filtered` tiverem rodado (precisa dos estados
reais logados por eles):

```bash
python experiments/invariance_test.py --logs-dir logs_round2 --cap-per-source 150 --permutations-per-state 6
```

Gera `logs_round2/invariance_test.jsonl` (todos os resultados, por estado) e
`logs_round2/invariance_test_summary.json` (agregado por fonte).

## 3. Gerar o relatório da rodada 2

```bash
python experiments/report_round2.py
```

Lê `logs_round2/` (rodada 2) e `logs/` (rodada 1, somente leitura) e escreve
`reports/round2_report.md`: métricas agregadas, comparação pareada com IC
95% contra o baseline, resumo do teste de invariância, comparação rodada 1 x
rodada 2, e o veredito do critério de avanço ao minecraft-mbot.

## Notas

- Os thresholds de confiança (0.60/0.75/0.90) só afetam `julia_filtered_fallback`.
- "Munição consumida" usa a mesma correção da rodada 1 (ignora saltos por
  troca automática de arma do Doom ao pegar um item).
- O teste de invariância usa o modelo Julia-1 real -- não é uma estimativa
  nem uma simulação.
