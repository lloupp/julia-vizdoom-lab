# Rodada 3B — protocolo nativo/recomendado por modelo

A Rodada 3 original permanece intacta. Esta rodada existe porque os resultados
da Rodada 3 mostraram um sinal anormal no Laya: zero ataques e zero munição
consumida.

## Correção aplicada ao Laya

A documentação atual do Laya informa que:

- `laya-typed-decisions` é especializado em quatro workflows específicos e não
  deve ser imposto como padrão em um domínio arbitrário;
- `noul` pode seguir os rótulos literais `false`/`true` em vez do estado;
- quando isso ocorrer, o workaround recomendado é expressar a mesma decisão como
  `choice` de duas opções com chaves neutras.

Por isso a Rodada 3B usa:

```
Julia:
  state -> noul -> small choice

Laya:
  state -> neutral A/B choice -> normalize to P(true) -> small choice
```

O Laya usa `Router` sem override de checkpoint. Como o benchmark é em inglês,
o roteador deve selecionar o checkpoint geral inglês; o modelo efetivamente
selecionado é registrado nos logs e no relatório.

## O que não muda

- mesmo VizDoom;
- mesmas 50 seeds;
- mesmas ações;
- mesmo estado estruturado;
- mesma hierarquia estratégica;
- mesmo cache orientado a eventos;
- mesmo executor determinístico;
- mesmas regras anti-loop;
- nenhum threshold ajustado após observar resultados.

## Testes

```bash
PYTHONPATH=. USE_TF=0 python -m pytest -q
```

## Benchmark

```bash
bash scripts/run_round3b_all.sh
```

Saídas:

```
logs_round3b/
reports/round3b_report.md
```

O relatório também mostra:

- taxa de ataque quando `atacar` estava disponível;
- frequência de `engage_enemy` positivo;
- checkpoint efetivamente escolhido pelo Router do Laya.
