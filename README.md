# julia-vizdoom-lab

Testa o [SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1) (modelo de decisão de 144.3M parâmetros) como camada de decisão em um ambiente controlado (VizDoom), antes de integrá-lo ao bot de Minecraft em `lloupp/minecraft-mbot`.

## Pipeline

```
estado do jogo (GameState) → agente de decisão → ação + confiança → executor determinístico → novo estado
```

- **Estado mínimo** (`decision/state.py`): vida, munição, inimigos visíveis, distância do inimigo, kit médico visível, munição visível.
- **Ações** (`decision/actions.py`): `atacar`, `fugir`, `buscar_vida`, `buscar_municao`, `explorar`, `esperar`.
- **Agentes** (`decision/agents/`):
  - `RuleBasedAgent`: baseline 100% determinístico (sem modelo).
  - `JuliaAgent`: chama o Julia-1 real localmente (CPU), pede uma decisão do tipo `choice` entre as ações disponíveis e usa a `probabilities`/`max_probability` retornada como confiança.
  - `JuliaWithFallbackAgent`: usa Julia-1; se a confiança ficar abaixo de um threshold configurável (ou o modelo falhar), usa `RuleBasedAgent` como fallback.
  - `AntiLoopGuard`: decorator aplicado às 3 variantes; detecta quando o agente repete a mesma ação por N passos sem o estado do jogo mudar, e força uma alternativa determinística (evita loops infinitos).
- **Executor** (`vizdoom_env/executor.py`): função pura ação → botões do VizDoom (sem aleatoriedade).
- **Ambiente** (`vizdoom_env/wrapper.py`): extrai o estado mínimo do VizDoom (cenário `deathmatch.wad`, já incluído no pacote `vizdoom`) via variáveis de jogo e o *labels buffer* (categorias `Monster`/`Health`/`Ammo`).
- **Logging** (`decision/logging.py`): toda decisão é gravada em JSONL (estado, ação, confiança, fonte, latência, fallback, erro).

`decision/` não depende de VizDoom — é a camada pensada para ser reaproveitada em `lloupp/minecraft-mbot` (basta produzir um `GameState` a partir do estado do Minecraft e implementar um executor equivalente).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup_julia_model.py   # baixa os pesos reais (~613 MiB) e instala o pacote `julia`
```

## Rodar os testes

```bash
PYTHONPATH=. python -m pytest -q
```

## Rodar o experimento comparativo

```bash
PYTHONPATH=. python experiments/run_experiment.py --episodes 15 --episode-timeout 2400
PYTHONPATH=. python experiments/report.py
```

Gera `logs/<variant>/{decisions.jsonl,episodes_summary.jsonl}` (dados brutos reais) e `reports/comparative_report.md` (relatório calculado 100% a partir desses logs, sem edição manual). Veja `docs/REPRODUCE.md` para o passo a passo completo e os parâmetros exatos usados na rodada oficial.

## Resultado (rodada 1)

O relatório em [`reports/comparative_report.md`](reports/comparative_report.md) compara as 3 variantes (regras / Julia-1 / Julia-1+fallback) em 15 episódios pareados cada, com tempo de sobrevivência, inimigos eliminados, dano recebido, munição consumida, confiança média, taxa de fallback, latência do modelo (p50/p95) e taxa de decisões inválidas.

## Rodada 2: filtro de ações, teste de invariância e estatística com IC 95%

A rodada 2 (`docs/REPRODUCE_ROUND2.md`) não altera nada da rodada 1 -- adiciona 4 agentes (`rules`, `julia_raw`, `julia_filtered`, `julia_filtered_fallback` em 3 thresholds), um filtro determinístico de ações (`decision/agents/filter.py`) que só *restringe* o que o Julia-1 pode escolher, um teste real de invariância à ordem das opções (`experiments/invariance_test.py`), comparação estatística pareada com IC 95% (`experiments/stats.py`), 50 seeds por variante (20 repetidas da rodada 1 + 30 novas nunca usadas no desenvolvimento) e um critério objetivo de avanço ao `minecraft-mbot`.

Resultado em [`reports/round2_report.md`](reports/round2_report.md): o teste de invariância encontrou que a escolha do Julia-1 muda em ~94-96% dos estados reais testados apenas por reordenar as mesmas opções (ex.: a mesma pergunta recebe "esperar" com 98% de "confiança" numa ordem e "explorar" com 83% na ordem invertida) -- por isso o veredito da rodada 2 é não avançar ainda para o Minecraft, apesar de sobrevivência e kills não piorarem significativamente contra o baseline.

## agent_decision_eval/: Laya-multilingual vs. Julia-1 para ações de agente de código

Subprojeto independente (`agent_decision_eval/README.md`) -- mesmo espírito ("testar o modelo de decisão antes de confiar nele"), domínio diferente: roteamento de ferramentas de um agente de código (`answer`/`read`/`grep`/`find`/`ls`/`write`/`edit`/`bash`/`web_search`/`stop`) para uso no Pi Agent, não VizDoom/Minecraft. Compara Laya sozinho, Julia sozinho, os dois em paralelo e Laya-principal-com-fallback-no-Julia em >=500 decisões reais por modo. Resultado em [`agent_decision_eval/reports/agent_decision_report.md`](agent_decision_eval/reports/agent_decision_report.md): nenhuma das 4 configurações atinge a barra de accuracy exigida (85% geral / 95% em write-edit-bash) neste vocabulário de ações -- nenhuma é recomendada para produção no estado atual.


## Rodada 3: Julia-1 vs Laya no VizDoom, usando a interface recomendada

A rodada 3 é isolada em `round3/`, `experiments/run_experiment_v3.py` e `logs_round3/`. Ela corrige o protocolo de uso: Julia usa perguntas tipadas nomeadas e sem gate baseado em `max_probability`; Laya usa o `Router` recomendado com `model="typed-decisions"`; ambos recebem o mesmo estado estruturado e uma hierarquia `noul -> choice` em ordem fixa, com decisões orientadas a eventos em vez de uma nova inferência a cada loop.

Passo a passo: [`docs/REPRODUCE_ROUND3.md`](docs/REPRODUCE_ROUND3.md).


## Rodada 3B: correção model-native do Laya

A Rodada 3 revelou `0` ataques para o Laya. A Rodada 3B preserva a execução
anterior e corrige duas escolhas de integração conforme a documentação do
modelo: não força o checkpoint especializado `typed-decisions` em VizDoom e
substitui `noul` por `choice` binário com chaves neutras no backend Laya,
normalizando o resultado de volta para a mesma hierarquia usada no jogo.

Reprodução: [`docs/REPRODUCE_ROUND3B.md`](docs/REPRODUCE_ROUND3B.md).


## Rodada 3C: direct choice sem gate booleano

A Rodada 3B mostrou que `survival_priority` permanecia positivo em 100% das
chamadas frescas do Laya e, por estar antes de `engage_enemy`, bloqueava o
ramo de ataque. A Rodada 3C remove essa arquitetura: seleção de ação é tratada
como uma única `choice` entre ações válidas, pois elas são mutuamente
exclusivas. Julia e Laya recebem exatamente o mesmo estado, critérios e ordem.

Reprodução: [`docs/REPRODUCE_ROUND3C.md`](docs/REPRODUCE_ROUND3C.md).
