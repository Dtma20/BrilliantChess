# Estrategia de testes

## Piramide

1. **Unitarios** (`tests/unit`) — funcoes puras: pontos esperados, material,
   portoes, pontuacao, configuracao, `doctor`, CLI.
2. **Contrato** (`tests/contract`) — o port `ChessEngine`. As mesmas asserces
   devem valer para o `ScriptedEngine` e para o adapter real do Stockfish.
3. **Integracao** (`tests/integration`) — marcadas `slow`, pulam sozinhas quando
   o Stockfish nao esta instalado.
4. **Golden** (`tests/golden`) — fixtures versionadas com orcamento fixo em nos.
5. **Propriedade** (`tests/property`) — invariantes com Hypothesis.

## Fake do motor

`tests/fakes/scripted_engine.ScriptedEngine` responde a partir de uma fixture
indexada por `(FEN, root_moves, nos)`. Permite exercitar mudanca de rank entre
estagios, drift, crash com retry, mate e multiplas PVs sem o binario real. Ele
falha em vez de inventar resultado para posicoes desconhecidas.

Nao faca mock de metodos internos: teste contratos observaveis.

## Invariantes verificadas por propriedade

- `EP` sempre em `[0, 1]` para WDL, centipawns e mate;
- inverter o ponto de vista duas vezes e identidade;
- `EP_loss` nunca negativa;
- aumentar `EP_loss` nunca aumenta o componente de qualidade;
- pontuacao final sempre em `[0, 100]`;
- candidata em posicao ja ganha nunca e declarada brilhante nem selecionavel.

## Golden fixtures

Schema e regras em `tests/fixtures/positions/README.md`. **Nunca** altere a
expectativa de uma fixture apenas porque a implementacao falhou. Toda mudanca
precisa de justificativa escrita; mudanca de regra precisa de ADR.

## Determinismo

Use limite por **nos**, nunca por tempo, em golden tests e geracao de dataset.
`AnalysisBudget.is_deterministic` existe para tornar isso verificavel. Nos
testes de integracao fixe `Threads=1` e Hash pequeno para reduzir variabilidade.

## Comandos

```bash
uv run pytest
```

```bash
uv run pytest --cov --cov-report=term-missing
```

```bash
uv run pytest -m slow
```

## Testes da interface web

`tests/unit/test_web_api.py` sobe o app com `TestClient` e substitui
`app.state.engine_session` por `tests/fakes/stub_engine.StubSession`. Nenhum
processo do Stockfish e iniciado: os testes verificam o contrato JSON, os
codigos HTTP, o fluxo da partida e a geracao das setas.

`tests/integration/test_stockfish_engine.py` cobre o que so o motor real pode
provar: identidade e NNUE, MultiPV, `root_moves`, ponto de vista por cor, WDL,
jogada com forca limitada e a restauracao de forca total antes da analise.

## Metas de cobertura

Dominio >= 90%, global >= 80%.
