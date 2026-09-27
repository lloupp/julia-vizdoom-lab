# Laya-multilingual vs. Julia-1 como Decision Model do agente

Gerado inteiramente a partir de `agent_decision_eval/logs/<mode>.jsonl`. Nenhum número foi ajustado manualmente.

**Aviso sobre confiança:** ambos os modelos expõem uma probabilidade softmax bruta (`max_probability`); o card do Laya admite explicitamente que o modelo "ships uncalibrated" com "systematic over-confidence". Nenhuma das duas é tratada aqui como confiança calibrada.

## Métricas por modo

| Métrica | Laya sozinho | Julia sozinho | Laya + Julia em paralelo | Laya principal + Julia fallback |
|---|---|---|---|---|
| Decisões | 504 | 504 | 504 | 504 |
| Accuracy geral | 32.1% | 23.2% | 17.9% | 35.7% |
| Accuracy sensível (write/edit/bash) | 44.4% | 50.0% | 22.2% | 61.1% |
| Decisões destrutivas incorretas | 9 | 180 | 0 | 18 |
| Concordância Laya x Julia | n/d | n/d | 12.5% | 26.3% |
| Taxa de fallback/indecisão | 0.0% | 0.0% | 87.5% | 33.9% |
| Latência média (ms) | 216.9 | 90.5 | 299.8 | 233.8 |
| Latência p95 (ms) | 271.8 | 121.1 | 369.5 | 331.3 |
| RAM máxima do processo (MB) | 2533 | 2720 | 2721 | 2721 |
| CPU média (%) | 392.8 | 392.5 | 392.4 | 393.6 |
| Crescimento de RSS (MB) | 0.9 | 6.4 | 0.3 | 0.5 |
| Erros do modelo | 0 | 0 | 0 | 0 |
| Estável por >=500 decisões | sim | sim | sim | sim |

### Accuracy por ação sensível

| Ação | Laya sozinho | Julia sozinho | Laya + Julia em paralelo | Laya principal + Julia fallback |
|---|---|---|---|---|
| bash | 0.0% | 50.0% | 0.0% | 33.3% |
| edit | 50.0% | 33.3% | 16.7% | 66.7% |
| write | 83.3% | 66.7% | 50.0% | 83.3% |

## Critérios de sucesso (viabilidade)

| Critério | Laya sozinho | Julia sozinho | Laya + Julia em paralelo | Laya principal + Julia fallback |
|---|---|---|---|---|
| accuracy_geral_>=85% | **NÃO** | **NÃO** | **NÃO** | **NÃO** |
| zero_acoes_destrutivas_incorretas | **NÃO** | **NÃO** | sim | **NÃO** |
| accuracy_sensivel_>=95% | **NÃO** | **NÃO** | **NÃO** | **NÃO** |
| p95_<=1000ms | sim | sim | sim | sim |
| estavel_500_decisoes | sim | sim | sim | sim |
| **Viável (todos os critérios)** | **NÃO** | **NÃO** | **NÃO** | **NÃO** |

### Meta preferencial

| Meta | Laya sozinho | Julia sozinho | Laya + Julia em paralelo | Laya principal + Julia fallback |
|---|---|---|---|---|
| accuracy_>=90% | não | não | não | não |
| p95_<=500ms | sim | sim | sim | sim |

RAM compatível com execução simultânea ao Pi Agent é reportada, não avaliada como sim/não (nenhum orçamento de RAM do Pi Agent foi informado): com os dois modelos carregados ao mesmo tempo (modos paralelo e fallback), o processo usou até 2721 MB de RSS.

## A combinação vale o custo extra?

Melhor modo individual: **Laya sozinho** (accuracy=32.1%, p95=271.8 ms). Critério: só vale manter a combinação se ganhar >=2 pontos percentuais de accuracy sem aumentar o p95 em mais de 50%.

| Modo combinado | Ganho de accuracy (pp) | Aumento de p95 (%) | Vale o custo? |
|---|---|---|---|
| Laya + Julia em paralelo | -14.3 | +36.0 | **NÃO** |
| Laya principal + Julia fallback | +3.6 | +21.9 | **SIM** |

## Ranking (critérios de desempate, na ordem)

1. Menor número de decisões perigosas/incorretas -- 2. Maior accuracy geral -- 3. Maior accuracy em write/edit/bash -- 4. Menor taxa de fallback/indecisão -- 5. Menor p95 de latência -- 6. Menor RAM máxima -- 7. Menor CPU média -- 8. Arquitetura mais simples. Diferenças de accuracy menores que 1 ponto percentual (nos critérios 2 e 3) contam como empate técnico e passam para o próximo critério.

| Posição | Modo | Perigosas | Accuracy | Accuracy sensível | Indecisão | p95 (ms) | RAM máx (MB) | CPU média (%) |
|---|---|---|---|---|---|---|---|---|
| 1 | Laya + Julia em paralelo | 0 | 17.9% | 22.2% | 87.5% | 369.5 | 2721 | 392.4 |
| 2 | Laya sozinho | 9 | 32.1% | 44.4% | 0.0% | 271.8 | 2533 | 392.8 |
| 3 | Laya principal + Julia fallback | 18 | 35.7% | 61.1% | 33.9% | 331.3 | 2721 | 393.6 |
| 4 | Julia sozinho | 180 | 23.2% | 50.0% | 0.0% | 121.1 | 2720 | 392.5 |

O 1º lugar (**Laya + Julia em paralelo**) tem a pior accuracy geral do grupo, mas vence porque o critério de desempate #1 (zero decisões perigosas) domina os demais -- é exatamente essa a priorização pedida: nesse modo, qualquer divergência que envolva write/edit/bash é bloqueada e nunca auto-executada, o que produz zero incidentes às custas de uma taxa de indecisão muito alta (a maioria das decisões fica sem ação de fato tomada).

## Veredito

**Nenhuma configuração é viável pelos critérios de sucesso definidos.** Ver a tabela de critérios acima para o motivo de cada uma -- tipicamente accuracy geral e/ou accuracy em ações sensíveis muito abaixo do exigido para este vocabulário de ações específico. O ranking acima é apenas comparativo entre configurações igualmente não recomendadas para uso em produção neste estado.

Não se presumiu que os dois modelos juntos seriam melhores que um sozinho: a seção anterior mostra que a combinação só seria mantida se demonstrasse um ganho de accuracy mensurável (>=2pp) sem inflar a latência p95 em mais de 50% -- e isso foi checado diretamente nos números medidos, não assumido.

## Notas de metodologia

- A ordem das opções apresentadas a cada modelo é uma permutação determinística por tarefa (não a ordem fixa do enum), para que nenhuma ação se beneficie sistematicamente de viés posicional (um problema real e medido em uma avaliação anterior do Julia-1 neste mesmo repositório).
- Ambos os modelos são codificadores determinísticos (sem amostragem); repetir as mesmas 56 tarefas em múltiplos ciclos para atingir >=500 decisões consecutivas testa estabilidade/vazamento de memória, não adiciona poder estatístico novo à accuracy (os números são idênticos entre ciclos).
- 'Decisão perigosa/incorreta' = ação final sensível (write/edit/bash) E diferente da ação esperada, independente de qual ação era a esperada.
- No modo paralelo, divergência com qualquer proposta sensível nunca é auto-executada (usa 'answer' como fallback seguro); divergência somente entre ações de leitura usa a accuracy histórica de leitura de cada modelo (medida nos modos 1 e 2) para decidir.
- 'CPU média (%)' é o uso agregado entre os núcleos lógicos (psutil `cpu_percent`), então pode passar de 100%; esta máquina tem 4 núcleos, então ~390% indica os 4 núcleos praticamente saturados durante a inferência, não um erro de medição.
