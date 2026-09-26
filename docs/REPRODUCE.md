# Como reproduzir o experimento

## 1. Requisitos

- Python 3.11+
- ~1.5 GB de disco livre (venv + dependências ~6 GB se incluir o build padrão do PyTorch com CUDA; troque para o índice CPU-only do PyTorch abaixo se quiser algo mais enxuto)
- CPU apenas — nenhuma GPU é necessária (o Julia-1 roda em CPU nesta configuração)

## 2. Ambiente

```bash
cd julia-vizdoom-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Para uma instalação mais enxuta do PyTorch (sem as dependências CUDA, que não são usadas em CPU):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## 3. Baixar o modelo Julia-1 real

```bash
python scripts/setup_julia_model.py
```

Isso baixa os pesos reais de `SupersonicLabs/Julia-1` (~613 MiB) para `models/Julia-1/` (gitignored) e instala o pacote `julia` (editable) a partir do próprio repositório baixado. Sem esse passo, `JuliaAgent` levanta `JuliaUnavailableError` com uma mensagem explicando o que fazer.

## 4. Rodar os testes unitários

```bash
PYTHONPATH=. python -m pytest -q
```

Os testes não dependem do VizDoom nem do modelo Julia-1 (usam agentes reais para as regras/fallback/anti-loop, e um stub para os testes que envolvem "Julia" — o `JuliaAgent` real só é exercitado no experimento fim-a-fim).

## 5. Rodar o experimento completo (a rodada oficial usou estes parâmetros)

```bash
PYTHONPATH=. python experiments/run_experiment.py \
    --episodes 15 \
    --seed-base 1000 \
    --frame-skip 8 \
    --episode-timeout 2400 \
    --confidence-threshold 0.6 \
    --out-dir logs
```

- `--episodes 15`: 15 episódios por variante (45 no total).
- `--seed-base 1000`: episódio `i` de cada variante usa a seed `1000 + i` — mesma condição inicial do VizDoom entre variantes (a partir do momento em que as ações divergem, os estados também divergem).
- `--frame-skip 8`: cada decisão do agente é sustentada por 8 tics do motor (~0.23 s de jogo).
- `--episode-timeout 2400`: ~68.6 s de jogo por episódio (tempo suficiente para engajar inimigos e coletar itens no cenário `deathmatch.wad`).
- `--confidence-threshold 0.6`: usado apenas pela variante `julia_fallback`.

Tempo esperado: ~4 minutos no total (rules é quase instantâneo; julia/julia_fallback chamam o modelo real a cada decisão, ~35-40 ms/chamada em CPU).

Saída: `logs/<variant>/decisions.jsonl` (uma linha por decisão) e `logs/<variant>/episodes_summary.jsonl` (uma linha por episódio), para `variant` em `rules`, `julia`, `julia_fallback`.

## 6. Gerar o relatório comparativo

```bash
PYTHONPATH=. python experiments/report.py --logs-dir logs --out reports/comparative_report.md
```

O relatório é calculado inteiramente a partir dos arquivos JSONL acima (`experiments/metrics.py` + `experiments/report.py`) — nenhum número é digitado manualmente.

## 7. Rodar só uma variante (opcional, mais rápido para depurar)

```bash
PYTHONPATH=. python experiments/run_experiment.py --episodes 3 --variants rules
PYTHONPATH=. python experiments/run_experiment.py --episodes 3 --variants julia
```

## Notas sobre o cenário

- Cenário: `deathmatch.wad` (bundled com o pacote `vizdoom`, mapa `map01`). Foi escolhido por ser o único cenário padrão do VizDoom com monstros, itens de vida (`Stimpack`/`Medikit`/`HealthBonus`) e munição (`ClipBox`/`ShellBox`/`RocketBox`) simultaneamente, com movimento livre do jogador.
- Detecção de inimigos/itens usa o *labels buffer* do VizDoom e a categoria semântica de cada label (`Monster`/`Health`/`Ammo`), não uma lista fixa de nomes — então funciona mesmo se o mapa tiver outros tipos de monstro/item.
- "Munição" no estado é a munição da arma atualmente equipada. O Doom troca de arma automaticamente ao pegar uma nova (comportamento padrão do motor); a métrica "munição consumida" ignora esses saltos de troca de arma (só conta quedas enquanto a arma equipada não muda), para não confundir troca de arma com disparo real.
