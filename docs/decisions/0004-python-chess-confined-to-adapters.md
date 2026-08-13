# 0004 — `python-chess` confinado a adapters; dominio opera sobre snapshots

Data: 2026-08-12
Estado: aceita

## Contexto

A especificacao exige que o adapter nao vaze objetos de `python-chess` para o
dominio. Ao mesmo tempo, o dominio precisa contar material antes e depois de uma
jogada, cobrindo captura, promocao, en passant e roque — casos onde as regras do
xadrez sao sutis e reimplementa-las seria um erro.

## Decisao

O dominio nao le tabuleiros. Ele opera sobre `PiecePlacement`, um mapeamento de
casa algebrica para `Piece(color, piece_type)`, produzido por um adapter que usa
`python-chess`. `material_for`, `material_balance` e `material_delta` sao
aritmetica pura sobre esses snapshots.

`ruff` bane o import de `chess` fora de `adapters/`
(`flake8-tidy-imports.banned-api`).

## Alternativas consideradas

- **Permitir `python-chess` dentro de `domain/`.** Rejeitado: quebraria a
  fronteira exigida e faria os testes do dominio dependerem da biblioteca.
- **Reimplementar geracao de lances no dominio.** Rejeitado: risco enorme de bug
  em en passant, promocao e roque, exatamente os itens do checklist de revisao.

## Consequencias

- Testes de material rodam sem motor e sem biblioteca de xadrez, com snapshots
  explicitos: captura, en passant, promocao, subpromocao, roque e troca
  equivalente ja estao cobertos.
- A correcao de en passant, promocao e roque passa a ser responsabilidade da
  conversao no adapter, que sera coberta por testes de contrato na Entrega 2.
- O dominio ganha um tipo proprio (`PositionSnapshot`) em vez de depender de
  `chess.Board`.
