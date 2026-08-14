# Arquitetura

## Regra de dependencia

As dependencias apontam para dentro. Nada em `domain/` conhece infraestrutura.

```mermaid
flowchart TD
    CLI["interfaces/cli"] --> APP["application"]
    WEB["interfaces/web"] --> APP
    APP --> DOMAIN["domain"]
    APP --> PORTS["ports"]
    ADAPTERS["adapters (Stockfish, tabuleiro, SQLite, PGN)"] --> PORTS
    ADAPTERS --> DOMAIN
    BOOTSTRAP["bootstrap"] --> APP
    BOOTSTRAP --> ADAPTERS
```

Verificacoes automaticas:

- `ruff` bane o import de `chess` fora de `adapters/` (regra
  `flake8-tidy-imports.banned-api`);
- `domain/` nao importa `pydantic`: a validacao de YAML vive em
  `bootstrap/config.py` e converte para dataclasses puras de
  `domain/rule_set.py`.

## Fronteiras principais

| Fronteira | Contrato | Implementacao atual |
| --- | --- | --- |
| Busca e avaliacao | `ports/engine.ChessEngine` | `adapters/stockfish/client.StockfishEngine` e `tests/fakes/ScriptedEngine` |
| Jogar uma partida | `ports/engine.PlayableEngine` | mesmo adapter, com `UCI_LimitStrength` |
| Regras de tabuleiro | `ports/board.BoardService` | `adapters/board/service.PythonChessBoardService` |
| Persistencia e cache | `ports/analysis_repository.AnalysisRepository` | Entrega 7 (SQLite) |
| Fonte de partidas | `ports/game_source.GameSource` | Entrega 7 (PGN local) |
| Ranking neural futuro | `CandidateRanker` em `adapters/ml/` | Nao existe; so depois de baseline medido |

## Ciclo de vida do motor

O motor **nao** e guardado no `Container`. Cada caso de uso cria, usa e fecha o
motor com ciclo explicito, para que o processo seja encerrado mesmo em caso de
excecao. Estado global de motor ou configuracao e proibido.

No servidor web, `interfaces/web/engine_session.EngineSession` mantem um unico
processo, iniciado sob demanda e encerrado no `lifespan` do FastAPI. Acesso
concorrente e serializado pelo `RLock` interno do `StockfishEngine`, e endpoints
sincronos rodam na threadpool do FastAPI, entao nenhum pedido bloqueia o loop de
eventos.

Forca reduzida (`UCI_LimitStrength`/`UCI_Elo`) e um estado do processo. O adapter
restaura forca total antes de qualquer `analyze`, para que uma partida em nivel
iniciante nao contamine a analise seguinte. Ha teste de integracao para isso.

## Estagios de analise

1. **Shallow** (`strict_v2`) — MultiPV 5 com orcamento de 5.000 nos para medir rank e
   pontos esperados iniciais e fundamentar o portao de nao obviedade (`GATE_NON_OBVIOUS_001`).
2. **Discovery** — MultiPV amplo, orcamento moderado, encontra candidatas.
3. **Confirmation** — cada candidata promissora e reanalisada isoladamente com
   `root_moves=[candidata]` e orcamento maior. O rank usado pelos portoes vem
   daqui, nunca do MultiPV de discovery.
4. **Best Defense** — busca da melhor resposta adversaria para avaliar solidez do sacrificio.
5. **Stability** — candidatas proximas de limiar recebem orcamento maior; sem
   esse estagio, `GATE_STABILITY_001` fica indeterminado em vez de aprovado.

Os orcamentos por estagio vem de `Container.budget_for` ou da configuracao do
laboratorio e sao sempre expressos em nos, para reprodutibilidade.

## Resolucao de regras

O container carrega o perfil historico `strict_v1.yaml` e o perfil atual
`strict_v2.yaml`. A aplicacao resolve o conjunto de regras via
`container.rule_set_for(policy)`, garantindo que chamadas com `strict_v1`
mantenham a semantica de 7 portoes e que `strict_v2` utilize os 8 portoes
com avaliacao de trocas (`BoardService.exchange_lines`) e nao obviedade.

## Ponto de vista

Toda avaliacao e normalizada do ponto de vista de quem fez a jogada. Depois de
aplicar a candidata o lado a jogar muda; `NormalizedEvaluation.flipped()` existe
para tornar essa troca explicita e testavel, em vez de deixar o sinal inverter
silenciosamente. Ha testes para brancas e pretas.

## Exploracao de abertura

A camada de aplicacao conta com o servico `OpeningSelector` e o gerenciador
`OpeningSessionTracker` (na camada web). A suite de aberturas curada reside em
`adapters/opening_suite/` como dados JSON puros. Quando o duelo inicia em modo
exploratorio, o motor reproduz os lances da suite e, ao final da linha planejada,
realiza amostragem MultiPV com corte de perda de EP (`max_ep_loss`) e temperatura
softmax deterministica via semente `uint64`.

## Arquivos e tamanho

Meta de ate 250 linhas por modulo de producao, limite suave de 400. Uma
responsabilidade principal por arquivo. Sem `utils.py`, `helpers.py` ou
`common.py`.

