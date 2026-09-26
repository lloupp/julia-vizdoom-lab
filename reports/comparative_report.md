# Relatório comparativo: Julia-1 vs. baseline de regras (VizDoom)

Relatório gerado automaticamente a partir dos logs em `logs/<variant>/decisions.jsonl` e `episodes_summary.jsonl`. Nenhum número abaixo foi editado manualmente.

## Configuração do experimento

- **episodes_per_variant**: 15
- **seed_base**: 1000
- **frame_skip**: 8
- **episode_timeout**: 2400
- **confidence_threshold**: 0.6
- **variants**: ['rules', 'julia', 'julia_fallback']

## Métricas agregadas por variante

| Métrica | Somente regras (baseline) | Julia-1 (puro) | Julia-1 + fallback |
|---|---|---|---|
| Tempo de sobrevivência (s) | 27.5 | 35.9 | 36.7 |
| Inimigos eliminados | 5.20 | 4.27 | 5.00 |
| Dano recebido | 131.6 | 126.9 | 148.3 |
| Munição consumida | 37.0 | 18.3 | 29.7 |
| Decisões por episódio | 120.6 | 157.5 | 161.1 |
| Confiança média (ação executada) | 1.000 | 0.855 | 0.877 |
| Confiança média do modelo Julia-1 | n/d | 0.855 | 0.851 |
| Fallbacks (baixa confiança) por episódio | 0.00 | 0.00 | 9.53 |
| Taxa de fallback (baixa confiança) | 0.0% | 0.0% | 5.6% |
| Quebras de loop por episódio | 2.93 | 17.60 | 17.33 |
| Latência média do Julia-1 (ms) | 0.00 | 35.87 | 37.54 |
| Latência p95 do Julia-1 (ms) | 0.00 | 50.04 | 52.67 |
| Erros do modelo por episódio | 0.00 | 0.00 | 0.00 |
| Decisões inválidas por episódio | 0.00 | 0.00 | 0.00 |
| Taxa de morte (vs. timeout) | 100.0% | 93.3% | 100.0% |
| Episódios avaliados | 15 | 15 | 15 |

## Julia-1 melhora ou piora o agente, comparado ao baseline?

Variação percentual em relação ao baseline determinístico (`somente regras`); positivo = variante ficou acima do baseline.

| Métrica | Δ% Julia-1 (puro) | Δ% Julia-1 + fallback |
|---|---|---|
| Tempo de sobrevivência (s) | +30.6% (▲ melhor) | +33.6% (▲ melhor) |
| Inimigos eliminados | -17.9% (▼ pior) | -3.8% (▼ pior) |
| Dano recebido | -3.5% (▲ melhor) | +12.7% (▼ pior) |
| Munição consumida | -50.5% (▲ melhor) | -19.6% (▲ melhor) |
| Latência média do Julia-1 (ms) | n/d | n/d |
| Latência p95 do Julia-1 (ms) | n/d | n/d |
| Erros do modelo por episódio | n/d | n/d |
| Decisões inválidas por episódio | n/d | n/d |
| Taxa de morte (vs. timeout) | -6.7% (▲ melhor) | +0.0% (≈ igual) |

### Síntese objetiva

**Julia-1 (puro)** vs. baseline: melhora em 4 métrica(s) (Tempo de sobrevivência (s), Dano recebido, Munição consumida, Taxa de morte (vs. timeout)), piora em 1 métrica(s) (Inimigos eliminados), empata em 4.
**Julia-1 + fallback** vs. baseline: melhora em 2 métrica(s) (Tempo de sobrevivência (s), Munição consumida), piora em 2 métrica(s) (Inimigos eliminados, Dano recebido), empata em 5.

Contagem simples de métricas com direção definida (sobrevivência, kills, dano, munição, latência, erros, decisões inválidas, taxa de morte); não pondera a importância relativa de cada métrica para o caso de uso final -- essa ponderação cabe a quem for decidir se usa Julia-1 em produção.

## Notas de metodologia

- Cada episódio de cada variante usa a mesma seed pareada (`seed_base + episode_id`), controlando a condição inicial do VizDoom entre variantes; a partir do momento em que as decisões divergem, os estados do jogo naturalmente divergem também -- isso é o que está sendo medido.
- 'Confiança média (ação executada)' é 1.0 por definição para o baseline de regras (regras determinísticas não têm incerteza); a coluna 'Confiança média do modelo Julia-1' é a única comparável entre as variantes que usam o modelo.
- Latência do Julia-1 é medida por chamada real a `engine.predict(...)` rodando localmente em CPU; o baseline de regras não tem essa coluna por não invocar o modelo.
- 'Fallbacks (baixa confiança)' e 'Quebras de loop' são mecanismos independentes: o primeiro só existe em `julia_fallback` (confiança do modelo abaixo do threshold); o segundo (`AntiLoopGuard`) é aplicado igualmente às 3 variantes para evitar loops infinitos, por isso pode aparecer também no baseline de regras.
- 'Munição' é a munição da arma atualmente equipada (`SELECTED_WEAPON_AMMO`). O Doom troca de arma automaticamente ao pegar uma nova (comportamento padrão do motor); quando isso acontece, o valor de munição salta para o pool da nova arma. 'Munição consumida' ignora esses saltos (só conta quedas enquanto a arma equipada não muda), para não confundir troca de arma com disparo real.
