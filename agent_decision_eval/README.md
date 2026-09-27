# agent_decision_eval

Benchmark: [`convaiinnovations/laya-multilingual`](https://huggingface.co/convaiinnovations/laya-multilingual) vs. [`SupersonicLabs/Julia-1`](https://huggingface.co/SupersonicLabs/Julia-1) como *decision model* para o roteamento de ferramentas de um agente de código (ex.: Pi Agent), em 4 modos.

Subprojeto independente do restante do repositório (`decision/`, `vizdoom_env/`, `experiments/` são sobre o laboratório VizDoom Julia-1-vs-regras) — domínio diferente (ações de agente de código, não FPS), modelos diferentes, sem dependências cruzadas.

## Ações avaliadas

`answer`, `read`, `grep`, `find`, `ls`, `write`, `edit`, `bash`, `web_search`, `stop` -- as 3 primeiras sensíveis (`write`, `edit`, `bash`) recebem uma barra de accuracy mais alta e qualquer decisão sensível incorreta é contada como "perigosa".

## Os 4 modos

1. **`laya_only`** -- só o Laya-multilingual decide.
2. **`julia_only`** -- só o Julia-1 decide.
3. **`parallel`** -- os dois decidem; concordância usa a ação comum; divergência **nunca** combina as confidences por soma. Se qualquer lado propuser `write`/`edit`/`bash`, a divergência é bloqueada (usa `answer` como fallback seguro, nunca auto-executa); divergência só entre ações de leitura usa a accuracy histórica de leitura de cada modelo (medida nos modos 1 e 2) para desempatar.
4. **`primary_fallback`** -- Laya decide primeiro; se a confidence própria do Laya (`confidence`, não `max_probability`) ficar abaixo de um threshold configurável, usa o Julia-1 no lugar.

## Setup

Reusa o venv e o Julia-1 já baixados para o laboratório VizDoom deste mesmo repositório (`docs/REPRODUCE.md`). Falta só o Laya:

```bash
source .venv/bin/activate
pip install laya psutil
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('convaiinnovations/laya-multilingual', local_dir='models/laya-multilingual')"
```

## Rodar os testes

```bash
PYTHONPATH=. python -m pytest agent_decision_eval/tests -q
```

## Rodar a avaliação completa

```bash
PYTHONPATH=. python agent_decision_eval/run_eval.py --min-decisions 500 --confidence-threshold 0.75
PYTHONPATH=. python agent_decision_eval/report.py
```

- `--min-decisions 500`: cada modo repete as 56 tarefas em ciclos até acumular pelo menos 500 decisões consecutivas (critério de estabilidade/vazamento de memória). Ambos os modelos são codificadores determinísticos (sem amostragem), então os ciclos repetem os mesmos resultados -- os 500+ testam estabilidade do processo, não trazem novo poder estatístico.
- Cada decisão é logada com a ação esperada, a decisão final, probabilidades/confidence de cada modelo consultado, concordância, latência, RSS e CPU% no momento -- ver `agent_decision_eval/logs/<mode>.jsonl`.
- O modelo Laya demora ~90s para carregar na primeira vez (ambos os modelos são carregados uma única vez e reusados entre os 4 modos, nunca recarregados por modo).
- Tempo total esperado: ~7-8 min para os 4 modos com 500+ decisões cada nesta máquina (4 núcleos, CPU only).

Saída: `agent_decision_eval/logs/<mode>.jsonl` (bruto) e `agent_decision_eval/reports/agent_decision_report.md` (relatório final, calculado inteiramente a partir dos logs).

## Ordem das opções

A ordem em que as opções são apresentadas a cada modelo é uma permutação determinística por tarefa (`decision.actions.options_for_task`, hash estável do `task_id`), não a ordem fixa de declaração do enum -- uma avaliação anterior do Julia-1 neste mesmo repositório (`docs/REPRODUCE_ROUND2.md`) mediu viés de posição real e significativo nesse modelo, então usar sempre a mesma ordem para todas as ~500 decisões deixaria qualquer ação que caísse primeiro/última com uma vantagem sistemática não relacionada à qualidade real da decisão.

## Resultado

Ver [`reports/agent_decision_report.md`](reports/agent_decision_report.md).
