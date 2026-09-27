# Relatório rodada 3B: Julia-1 vs Laya no VizDoom

O Laya usa Router sem checkpoint especialista forçado e substitui noul por choice binário com chaves neutras A/B, normalizado de volta para P(true). Julia mantém noul nativo. O ambiente e o executor permanecem iguais.

## Resultados agregados

| Métrica | regras | Julia recomendado | Laya recomendado |
|---|---:|---:|---:|
| Sobrevivência (s) | 25.31 | 42.04 | 41.63 |
| Kills | 3.84 | 6.02 | 3.06 |
| Dano recebido | 140.70 | 168.12 | 192.90 |
| Munição consumida | 33.10 | 29.16 | 0.00 |
| Decisões/episódio | 111.14 | 184.28 | 182.64 |
| Chamadas de modelo/episódio | 0.00 | 97.70 | 127.54 |
| Cache hit rate | 0.0% | 67.6% | 53.9% |
| Ataque quando disponível | 97.2% | 60.4% | 0.0% |
| Latência média por refresh (ms) | n/d | 505.64 | 2849.04 |
| Latência p95 por refresh (ms) | n/d | 709.01 | 3863.30 |

## Ações executadas

| Ação | regras | Julia recomendado | Laya recomendado |
|---|---:|---:|---:|
| atacar | 2723 | 2443 | 0 |
| buscar_municao | 14 | 771 | 731 |
| buscar_vida | 362 | 2871 | 3962 |
| esperar | 94 | 968 | 76 |
| explorar | 2100 | 1847 | 2653 |
| fugir | 264 | 314 | 1710 |

## Sanity checks do protocolo

- Julia engage_enemy positivo: 61.1%
- Laya engage_enemy positivo: 35.0%
- Roteamento Laya observado: english=6377

## Comparação pareada vs regras (IC 95%)

### julia_recommended

- survival_seconds: +16.72 [11.75, 21.70] (significativo, n=50)
- kills: +2.18 [0.66, 3.70] (significativo, n=50)
- damage_taken: +27.42 [-4.11, 58.95] (não significativo, n=50)
- ammo_consumed: -3.94 [-10.68, 2.80] (não significativo, n=50)

### laya_recommended

- survival_seconds: +16.32 [11.06, 21.58] (significativo, n=50)
- kills: -0.78 [-2.19, 0.63] (não significativo, n=50)
- damage_taken: +52.20 [15.46, 88.94] (significativo, n=50)
- ammo_consumed: -33.10 [-38.01, -28.19] (significativo, n=50)

## Metodologia

- Julia: noul nativo + choice, sem usar max_probability como gate.
- Laya: Router automático no benchmark em inglês; nenhum typed-decisions forçado.
- Laya Boolean: choice A/B com descrições yes/no, normalizado para P(true).
- Nenhum threshold foi ajustado olhando os resultados do jogo.
- Ordem dos candidatos permanece fixa por pergunta.
- O executor VizDoom é idêntico nos três agentes.

