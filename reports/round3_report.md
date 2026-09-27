# Relatório rodada 3: Julia-1 vs Laya no VizDoom

Gerado somente a partir de logs_round3/. A rodada usa o mesmo ambiente, estado, ações, seeds, hierarquia noul -> choice, ordem fixa de candidatos e política orientada a eventos para os dois modelos.

## Resultados agregados

| Métrica | regras | Julia recomendado | Laya recomendado |
|---|---:|---:|---:|
| Sobrevivência (s) | 25.31 | 42.04 | 45.02 |
| Kills | 3.84 | 6.02 | 3.92 |
| Dano recebido | 140.70 | 168.12 | 232.54 |
| Munição consumida | 33.10 | 29.16 | 0.00 |
| Decisões/episódio | 111.14 | 184.28 | 197.32 |
| Chamadas de modelo/episódio | 0.00 | 97.70 | 105.84 |
| Cache hit rate | 0.0% | 67.6% | 64.4% |
| Latência média por refresh (ms) | n/d | 498.78 | 2907.29 |
| Latência p95 por refresh (ms) | n/d | 691.49 | 3967.98 |

## Ações executadas

| Ação | regras | Julia recomendado | Laya recomendado |
|---|---:|---:|---:|
| atacar | 2723 | 2443 | 0 |
| buscar_municao | 14 | 771 | 709 |
| buscar_vida | 362 | 2871 | 6061 |
| esperar | 94 | 968 | 89 |
| explorar | 2100 | 1847 | 2629 |
| fugir | 264 | 314 | 378 |

## Comparação pareada vs regras (IC 95%)

### julia_recommended

- survival_seconds: +16.72 [11.75, 21.70] (significativo, n=50)
- kills: +2.18 [0.66, 3.70] (significativo, n=50)
- damage_taken: +27.42 [-4.11, 58.95] (não significativo, n=50)
- ammo_consumed: -3.94 [-10.68, 2.80] (não significativo, n=50)

### laya_recommended

- survival_seconds: +19.71 [13.43, 25.98] (significativo, n=50)
- kills: +0.08 [-1.65, 1.81] (não significativo, n=50)
- damage_taken: +91.84 [45.03, 138.65] (significativo, n=50)
- ammo_consumed: -33.10 [-38.01, -28.19] (significativo, n=50)

## Metodologia relevante

- Julia usa a API de perguntas nomeadas com strict_encoding=True.
- Laya usa Router com override explícito model=typed-decisions.
- Perguntas Boolean noul têm descrições explícitas para false e true.
- As quatro perguntas Boolean são avaliadas em lote; depois há no máximo uma pequena choice.
- A ordem de candidatos é fixa e semântica. Não há embaralhamento durante o benchmark.
- max_probability da Julia é registrado como score bruto e não é usado como confiança calibrada nem como gate de fallback.
- O modelo só é consultado em mudança estratégica de estado ou após expirar a janela de cache.
- Regras, Julia e Laya executam exatamente o mesmo executor determinístico do VizDoom.

