# Relatório rodada 2: Julia-1 filtrada + fallback vs. baseline

Gerado inteiramente a partir de `logs_round2/<variant>/` (rodada 2, seeds 1000-1019 = fase A, 5000-5029 = fase B) e `logs/<variant>/` (rodada 1, **não alterada**). Nenhum número foi digitado manualmente.

**Aviso sobre 'confiança':** `max_probability` do Julia-1 é um score softmax bruto, não uma confiança calibrada -- o teste de invariância abaixo mostra exatamente por que isso importa (o modelo reporta "confiança" alta para respostas contraditórias dependendo só da ordem de apresentação das opções).

## Rodada 2 -- métricas agregadas (fase A + fase B, 50 seeds)

| Métrica | Regras (baseline) | Julia-1 (raw, sem filtro) | Julia-1 filtrada | Julia-1 filtrada + fallback (t=0.60) | Julia-1 filtrada + fallback (t=0.75) | Julia-1 filtrada + fallback (t=0.90) |
|---|---|---|---|---|---|---|
| Episódios | 50 | 50 | 50 | 50 | 50 | 50 |
| Sobrevivência (s) | 24.2 | 39.5 | 43.6 | 40.1 | 42.5 | 27.1 |
| Kills | 3.20 | 6.46 | 8.58 | 6.90 | 7.28 | 3.62 |
| Dano recebido | 133.9 | 141.8 | 174.0 | 174.8 | 165.0 | 144.1 |
| Munição consumida | 31.0 | 38.4 | 43.9 | 42.8 | 42.5 | 30.5 |
| Decisões/episódio | 106.3 | 173.5 | 191.3 | 175.9 | 186.5 | 119.1 |
| Distribuição de ações | atacar 49%, explorar 40%, buscar_vida 6%, fugir 3%, esperar 2%, buscar_municao 1% | esperar 30%, atacar 26%, explorar 18%, buscar_municao 13%, buscar_vida 12%, fugir 1% | atacar 28%, explorar 24%, buscar_vida 19%, buscar_municao 15%, esperar 11%, fugir 4% | atacar 29%, explorar 24%, buscar_vida 18%, buscar_municao 16%, esperar 9%, fugir 5% | explorar 30%, atacar 28%, buscar_vida 16%, buscar_municao 13%, esperar 8%, fugir 6% | atacar 44%, explorar 34%, buscar_vida 9%, fugir 7%, esperar 5%, buscar_municao 1% |
| Confiança média (executada) | 1.000 | 0.840 | 0.837 | 0.879 | 0.936 | 0.991 |
| Score médio do modelo (não calibrado) | n/d | 0.840 | 0.806 | 0.808 | 0.814 | 0.851 |
| Chamadas reais ao modelo/episódio | 0.0 | 173.5 | 160.1 | 147.2 | 157.0 | 102.7 |
| Taxa de ação forçada pelo filtro | 0.0% | 0.0% | 16.4% | 16.7% | 16.8% | 13.4% |
| Fallbacks (baixa confiança)/episódio | 0.00 | 0.00 | 0.00 | 15.84 | 47.04 | 52.16 |
| Taxa de fallback | 0.0% | 0.0% | 0.0% | 8.3% | 24.4% | 45.7% |
| Overrides anti-loop/episódio | 2.42 | 25.46 | 13.10 | 11.40 | 13.50 | 4.20 |
| ...dos quais partiram de 'esperar' | 0.00 | 19.34 | 3.14 | 2.64 | 3.76 | 1.82 |
| Latência média do modelo (ms) | n/d | 48.28 | 50.22 | 50.02 | 48.83 | 50.40 |
| Latência p95 do modelo (ms) | n/d | 68.23 | 68.87 | 67.84 | 67.07 | 67.48 |
| Concordância com as regras | 98.4% | 43.9% | 54.3% | 58.6% | 67.0% | 90.7% |
| Erros do modelo/episódio | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Decisões inválidas/episódio | 0.00 | 0.00 | 1.22 | 0.90 | 0.78 | 0.62 |
| Taxa de morte (vs. timeout) | 98.0% | 88.0% | 84.0% | 94.0% | 86.0% | 98.0% |

### Fase A (seeds 1000-1019, comparáveis à rodada 1) vs. fase B (30 seeds novas, nunca usadas no desenvolvimento)

| Métrica | Fase | Regras (baseline) | Julia-1 (raw, sem filtro) | Julia-1 filtrada | Julia-1 filtrada + fallback (t=0.60) | Julia-1 filtrada + fallback (t=0.75) | Julia-1 filtrada + fallback (t=0.90) |
|---|---|---|---|---|---|---|---|
| Sobrevivência (s) | A | 24.9 | 37.3 | 44.9 | 43.4 | 44.1 | 29.1 |
| Sobrevivência (s) | B | 23.7 | 41.0 | 42.8 | 37.9 | 41.5 | 25.8 |
| Kills | A | 4.35 | 5.65 | 8.80 | 8.55 | 7.80 | 4.35 |
| Kills | B | 2.43 | 7.00 | 8.43 | 5.80 | 6.93 | 3.13 |
| Dano recebido | A | 122.2 | 133.3 | 173.1 | 168.6 | 173.6 | 135.4 |
| Dano recebido | B | 141.6 | 147.5 | 174.6 | 178.9 | 159.2 | 149.8 |
| Concordância com as regras | A | 98.3% | 42.5% | 52.7% | 60.1% | 68.1% | 91.4% |
| Concordância com as regras | B | 98.5% | 44.8% | 55.3% | 57.7% | 66.3% | 90.1% |

## Rodada 2 -- comparação pareada vs. baseline (IC 95%, 50 seeds)

Pareado por seed (mesma seed = mesma condição inicial do VizDoom). 'PIOR' = IC 95% da diferença exclui zero E fica do lado ruim da métrica (sobrevivência/kills menores, ou dano/munição maiores).

### Julia-1 (raw, sem filtro) vs. Regras (baseline)

- **Tempo de sobrevivência (s)**: diff=15.34 IC95%=[10.87, 19.80] n=50 (SIGNIFICATIVO)
- **Inimigos eliminados**: diff=3.26 IC95%=[1.70, 4.82] n=50 (SIGNIFICATIVO)
- **Dano recebido**: diff=7.94 IC95%=[-15.92, 31.80] n=50 (não significativo)
- **Munição consumida**: diff=7.42 IC95%=[-5.08, 19.92] n=50 (não significativo)

### Julia-1 filtrada vs. Regras (baseline)

- **Tempo de sobrevivência (s)**: diff=19.45 IC95%=[13.73, 25.17] n=50 (SIGNIFICATIVO)
- **Inimigos eliminados**: diff=5.38 IC95%=[3.34, 7.42] n=50 (SIGNIFICATIVO)
- **Dano recebido**: diff=40.10 IC95%=[8.40, 71.80] n=50 (SIGNIFICATIVO — PIOR)
- **Munição consumida**: diff=12.94 IC95%=[2.02, 23.86] n=50 (SIGNIFICATIVO — PIOR)

### Julia-1 filtrada + fallback (t=0.60) vs. Regras (baseline)

- **Tempo de sobrevivência (s)**: diff=15.90 IC95%=[10.67, 21.14] n=50 (SIGNIFICATIVO)
- **Inimigos eliminados**: diff=3.70 IC95%=[1.88, 5.52] n=50 (SIGNIFICATIVO)
- **Dano recebido**: diff=40.90 IC95%=[8.98, 72.82] n=50 (SIGNIFICATIVO — PIOR)
- **Munição consumida**: diff=11.86 IC95%=[0.05, 23.67] n=50 (SIGNIFICATIVO — PIOR)

### Julia-1 filtrada + fallback (t=0.75) vs. Regras (baseline)

- **Tempo de sobrevivência (s)**: diff=18.35 IC95%=[12.16, 24.53] n=50 (SIGNIFICATIVO)
- **Inimigos eliminados**: diff=4.08 IC95%=[1.89, 6.27] n=50 (SIGNIFICATIVO)
- **Dano recebido**: diff=31.12 IC95%=[-4.57, 66.81] n=50 (não significativo)
- **Munição consumida**: diff=11.50 IC95%=[-2.16, 25.16] n=50 (não significativo)

### Julia-1 filtrada + fallback (t=0.90) vs. Regras (baseline)

- **Tempo de sobrevivência (s)**: diff=2.94 IC95%=[-0.46, 6.33] n=50 (não significativo)
- **Inimigos eliminados**: diff=0.42 IC95%=[-0.77, 1.61] n=50 (não significativo)
- **Dano recebido**: diff=10.20 IC95%=[-14.22, 34.62] n=50 (não significativo)
- **Munição consumida**: diff=-0.44 IC95%=[-4.34, 3.46] n=50 (não significativo)

## Teste de invariância à ordem das opções

Mesmo estado, mesmas opções, ordens diferentes -- quantas vezes a escolha do Julia-1 muda. Permutações determinísticas (rotações da lista original e da lista invertida), sem RNG.

| Fonte dos estados | Estados testados | Taxa de instabilidade | Fração majoritária média | Escolhas distintas (média) |
|---|---|---|---|---|
| julia_raw | 150 | 93.3% | 63.1% | 2.30 |
| julia_filtered | 150 | 96.0% | 64.7% | 2.29 |
| overall | 300 | 94.7% | 63.9% | 2.30 |

## Rodada 1 vs. rodada 2

Rodada 1 usou 15 seeds (1000-1014); rodada 2 reusa essas mesmas seeds na fase A (mais 5 seeds extras, 1015-1019, e 30 seeds novas na fase B). Para a comparação direta abaixo, a rodada 2 é restrita às 15 seeds 1000-1014 -- exatamente as que a rodada 1 rodou.

| Métrica | R1: Regras | R2: Regras | R1: Julia (puro) | R2: Julia raw | R2: Julia filtrada | R1: Julia+fallback | R2: Julia filtrada+fallback (t=0.60) |
|---|---|---|---|---|---|---|---|
| Tempo de sobrevivência (s) | 27.5 | 27.5 | 35.9 | 36.1 | 42.1 | 36.7 | 43.3 |
| Inimigos eliminados | 5.2 | 5.2 | 4.3 | 5.1 | 7.7 | 5.0 | 8.4 |
| Dano recebido | 131.6 | 131.6 | 126.9 | 137.7 | 160.1 | 148.3 | 177.3 |
| Munição consumida | 37.0 | 37.0 | 18.3 | 24.8 | 45.2 | 29.7 | 44.3 |

### O baseline em si mudou entre rodadas?

A rodada 2 aplica um limite anti-loop mais apertado especificamente para 'esperar' (3 em vez de 5) em **todas** as variantes, incluindo 'regras' -- então antes de atribuir qualquer diferença ao Julia-1, vale checar se isso sozinho já mudou o baseline, nas mesmas seeds:

- **Sobrevivência, R2-regras vs. R1-regras** (mesmas 15 seeds): diff=0.00 IC95%=[0.00, 0.00] n=15 (não significativo)
- **Kills, R2-regras vs. R1-regras** (mesmas 15 seeds): diff=0.00 IC95%=[0.00, 0.00] n=15 (não significativo)

## Critério de avanço ao minecraft-mbot

Critério: nem 'Julia-1 filtrada' nem 'Julia-1 filtrada + fallback' (em nenhum dos 3 thresholds) pode apresentar piora estatisticamente significativa (IC 95%, pareado por seed, n=50) em sobrevivência ou kills contra o baseline de regras, **e** deve demonstrar estabilidade razoável à ordem das opções, definida aqui como taxa de instabilidade $\leq$ 30% no teste de invariância.

Os 3 thresholds de `julia_filtered_fallback` reusam a taxa de instabilidade medida em `julia_filtered`: o threshold só decide se o sistema *aceita ou descarta* a resposta do Julia-1, não muda o que é oferecido a ele nem como ele decide -- a sensibilidade à ordem é uma propriedade da chamada ao modelo em si, idêntica nas 4 variantes filtradas.

| Variante | Sem piora significativa (sobrev./kills) | Instabilidade à ordem | Estável (≤30%) | Passa no critério |
|---|---|---|---|---|
| Julia-1 filtrada | sim | 96.0% | NÃO | **NÃO** |
| Julia-1 filtrada + fallback (t=0.60) | sim | 96.0% | NÃO | **NÃO** |
| Julia-1 filtrada + fallback (t=0.75) | sim | 96.0% | NÃO | **NÃO** |
| Julia-1 filtrada + fallback (t=0.90) | sim | 96.0% | NÃO | **NÃO** |

### Veredito

**Não avançar ainda.** Nenhuma variante filtrada passou nos dois requisitos simultaneamente. Ver a tabela acima para o motivo específico de cada uma (regressão estatística em sobrevivência/kills, instabilidade à ordem acima do limiar, ou ambos).

## Notas de metodologia

- 'Munição consumida' usa a mesma correção da rodada 1 (ignora saltos por troca automática de arma do Doom).
- 'Concordância com as regras' compara a ação executada com o que `RuleBasedAgent` faria a partir do mesmíssimo (estado, ações disponíveis) -- é só um diagnóstico, nunca influencia a execução.
- Estatísticas pareadas usam a distribuição t de Student (não a normal) para o IC de 95%, mais correta com n pequeno; ver `experiments/stats.py`.
- O teste de invariância chama o Julia-1 real (mesmo processo, mesmo modelo) com as mesmas opções em ordens diferentes -- não é uma simulação nem uma estimativa teórica.
