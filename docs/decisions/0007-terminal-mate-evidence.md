# 0007 - Mate terminal e evidencia completa

**Status:** Aceita

**Data:** 2026-08-13

## Contexto

O UCI pode devolver score de mate sem variante principal para uma posicao ja
encerrada. O adapter retorna corretamente uma analise vazia nesse caso. Porem,
o seletor `strict_v1` interpretava essa ausencia como falta de melhor defesa e
de estabilidade, tornando uma jogada de mate inelegivel e permitindo uma linha
nao-terminal de menor qualidade.

## Decisao

Se a candidata produz xeque-mate confirmado pelo `BoardService`, os portoes de
solidez e estabilidade sao aprovados sem nova busca: nao ha defesa legal nem
linha posterior a estabilizar. A excecao nao se aplica a afogamento ou outros
terminos. A selecao `near_brilliant` ordena primeiro pela qualidade objetiva
(`EP_loss`), depois por mate vencedor mais curto; score diagnostico e UCI sao
somente desempates posteriores.

## Consequencias

Mates legais deixam de ser descartados por ausencia esperada de PV. A politica
mantem auditoria explicita e nao trata terminos nao-vencedores como prova de
solidez.
