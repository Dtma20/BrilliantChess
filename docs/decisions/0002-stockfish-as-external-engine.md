# 0002 — Stockfish como motor externo atras de um port

Data: 2026-08-12
Estado: aceita

## Contexto

O projeto precisa de avaliacao forte e de linhas principais. Escrever um motor
proprio esta fora de escopo. O Stockfish e o padrao livre e usa CPU.

## Decisao

O Stockfish e executado como processo externo via UCI, atras do port
`ports/engine.ChessEngine`. O binario nao acompanha o repositorio: e localizado
por `BRILLIANT_CHESS_STOCKFISH`, por `engine.binary_path` na configuracao, ou
pelo PATH. A identidade do motor (nome, versao, SHA-256, NNUE, opcoes) entra na
chave de cache.

O motor nao e guardado em estado global nem no `Container`; cada caso de uso
controla o ciclo de vida e garante encerramento mesmo com excecao.

A RTX 5060 nao participa do MVP. Nao ha codigo CUDA para o motor.

## Alternativas consideradas

- **Vincular a biblioteca do Stockfish no processo.** Rejeitado: acopla o
  binario ao projeto, complica licenciamento e dificulta trocar de versao.
- **Guardar um motor unico global reutilizado.** Rejeitado: um processo UCI nao
  pode ser compartilhado simultaneamente sem coordenacao, e vazamentos de
  processo sao dificeis de diagnosticar.

## Consequencias

- O `doctor` precisa localizar e validar o binario; sem ele o projeto falha de
  forma clara, com codigo de saida diferente de zero.
- Trocar a versao do motor invalida o cache automaticamente.
- Paralelismo exige respeitar `workers x threads <= CPUs logicas`, verificado
  pelo `doctor`.
- O projeto herda obrigacoes de GPL (ver ADR 0003).
