# Rodada 3 — uso recomendado de Julia-1 e Laya no VizDoom

Esta rodada é aditiva. Nada em `logs/`, `logs_round2/`, `run_experiment.py`
ou `run_experiment_v2.py` é alterado.

## O que foi corrigido

A rodada 3 testa os dois modelos no mesmo VizDoom, mas aproxima a integração
da interface recomendada pelos próprios projetos:

- **Julia-1:** API `state + named typed questions`, `strict_encoding=True`,
  perguntas `noul` com critérios descritivos e `choice` com candidatos
  explícitos e claros. `max_probability` é apenas score bruto, nunca gate de
  confiança.
- **Laya:** `Router` (modo recomendado) com override
  `model="typed-decisions"`, adequado ao benchmark em inglês e a perguntas
  tipadas.
- **Ambos:** a mesma hierarquia `noul -> choice`, a mesma ordem fixa de ações,
  o mesmo estado estruturado, o mesmo executor e a mesma política de decisão
  orientada a eventos.

Não há embaralhamento de alternativas em runtime. Sensibilidade à ordem pode
continuar sendo medida como diagnóstico separado, mas não invalida por si só
um deployment cuja ordem é fixa.

## Arquitetura

```
VizDoom
  -> estado estruturado + ações realmente disponíveis
  -> 4 perguntas noul em UMA chamada
       survival_priority
       engage_enemy
       seek_health
       seek_ammo
  -> estreitamento hierárquico
  -> no máximo 1 choice pequeno, em ordem fixa
  -> ação estratégica
  -> executor determinístico
  -> mantém ação em cache até evento relevante / TTL
```

Eventos relevantes: mudança de faixa de vida, faixa de munição, presença ou
quantidade de inimigos, faixa de distância do inimigo, visibilidade de pickups
ou conjunto de ações disponíveis.

## Setup

Use Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup_julia_model.py
```

O Laya usa `Router`; o checkpoint `typed-decisions` é baixado/cacheado pelo
runtime na primeira chamada. `USE_TF=0` é definido no script completo para
evitar a sondagem de TensorFlow documentada pelo projeto Laya.

## Testes unitários

```bash
PYTHONPATH=. USE_TF=0 python -m pytest -q
```

## Benchmark completo

```bash
bash scripts/run_round3_all.sh
```

Por padrão cada variante roda as mesmas 50 seeds:

- fase A: 1000–1019;
- fase B: 7000–7029.

Saídas:

```
logs_round3/rules/
logs_round3/julia_recommended/
logs_round3/laya_recommended/
reports/round3_report.md
```

## Relatório sem rerodar episódios

```bash
PYTHONPATH=. python experiments/report_round3.py
```

Não ajuste números manualmente. O relatório deve ser regenerado apenas a
partir dos JSONL produzidos pela rodada.
