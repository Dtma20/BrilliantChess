# 0001 — Regras deterministicas antes de aprendizado de maquina

Data: 2026-08-12
Estado: aceita

## Contexto

O objetivo e decidir se uma jogada e "brilhante". A definicao publica do
Chess.com e qualitativa e a formula interna nao e conhecida. Existe a tentacao de
treinar um modelo diretamente sobre rotulos observados.

## Decisao

A classificacao e feita por portoes deterministicos e auditaveis
(`domain/gates.py`), com limiares em configuracao e versao das regras registrada
em cada analise. Aprendizado de maquina fica atras de um port e so entra depois
que existirem dataset confiavel, baseline medido e metrica a superar.

## Alternativas consideradas

- **Classificador aprendido desde o inicio.** Rejeitado: sem dataset confiavel,
  o modelo aprenderia ruido e nao seria explicavel.
- **Heuristica unica com um score continuo e um corte.** Rejeitado: perde a
  capacidade de dizer *qual* criterio falhou.

## Consequencias

- Toda decisao produz valores medidos, limiares, portoes e avisos.
- Mudar comportamento exige mudar configuracao ou regra explicita, nunca ajustar
  pesos opacos.
- O sistema pode responder `indeterminate` quando falta evidencia, em vez de
  chutar.
- O custo e mais codigo de regra e mais testes.
