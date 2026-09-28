# Rodada 3C — direct choice de ação

A Rodada 3B revelou que `survival_priority` ficava positivo em 100% das
chamadas do Laya. Isso não é tratado como falha do modelo: a pergunta era
abstrata e fazia parte do objetivo global ("sobreviver"), mas o código a usava
como gate de retorno antecipado.

## Correção conceitual

As ações do VizDoom são mutuamente exclusivas: o agente executa exatamente uma
ação estratégica por vez. A primitiva usada nesta rodada é portanto uma única
`choice` sobre as ações realmente válidas.

```
estado estruturado
  -> ações válidas
  -> choice única
       atacar
       fugir
       buscar_vida
       buscar_municao
       explorar
       esperar
  -> executor determinístico
```

Não há:

- `survival_priority`;
- gates `noul`;
- thresholds de confiança;
- seleção de checkpoint especialista do Laya;
- embaralhamento de alternativas.

## Modelos

### Julia

- `SupersonicLabs/Julia-1`;
- `strict_encoding=True`;
- `max_probability` é apenas logado como score bruto.

### Laya

- `Router` recomendado;
- sem override `typed-decisions`;
- benchmark em inglês, portanto o checkpoint efetivamente escolhido é
  registrado nos logs e relatório;
- `confidence` é registrada, mas não controla a execução.

## O que permanece idêntico

- VizDoom e deathmatch;
- 50 seeds: 1000–1019 e 7000–7029;
- estado de jogo;
- conjunto de ações;
- descrições das ações;
- ordem fixa;
- cache orientado a eventos;
- executor;
- anti-loop;
- métricas.

## Testes

```bash
PYTHONPATH=. USE_TF=0 python -m pytest -q
```

## Benchmark completo

```bash
bash scripts/run_round3c_all.sh
```

Saídas:

```
logs_round3c/
reports/round3c_report.md
```
