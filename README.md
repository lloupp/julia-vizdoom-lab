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

## Resultado

O relatório em [`reports/comparative_report.md`](reports/comparative_report.md) compara as 3 variantes (regras / Julia-1 / Julia-1+fallback) em 15 episódios pareados cada, com tempo de sobrevivência, inimigos eliminados, dano recebido, munição consumida, confiança média, taxa de fallback, latência do modelo (p50/p95) e taxa de decisões inválidas.
