# Brilliant Chess

Analisador e seletor de jogadas "brilhantes" para xadrez, construido sobre o
Stockfish e um conjunto de regras deterministicas e auditaveis.

O sistema responde duas perguntas diferentes, que nunca sao misturadas:

1. **Classificacao** — esta jogada e brilhante segundo a especificacao?
2. **Selecao** — entre as jogadas objetivamente seguras, qual maximiza brilhantismo?

## Aviso de fair play

Este projeto e para **analise offline, estudo, pesquisa e partidas entre motores**.

A partida ao vivo que existe aqui e contra o proprio motor, no tabuleiro deste
app. Ele nao le tabuleiros de outras telas, nao clica em jogadas fora dele mesmo,
nao cria overlays e nao se conecta a partida alguma em plataforma externa. Usar
assistencia de motor durante uma partida humana ao vivo e trapaca e viola os
termos de qualquer plataforma seria. Nao adicione essa capacidade a este
repositorio.

## Escopo e honestidade sobre o Chess.com

O padrao implementado se chama `strict_v1`, nao `chess_com_exact`.

A definicao publica do Chess.com (melhor ou quase melhor, bom sacrificio de
peca, posicao resultante nao ruim, posicao anterior nao ja ganha, tolerancia
variando com rating) orienta o desenho. A formula exata e os limiares internos
do Chess.com **nao sao publicos**. Portanto todos os limiares aqui sao hipoteses
de engenharia expostas em configuracao, versionadas em cada analise, e
coincidencia com o Chess.com nunca e apresentada como garantia.

Referencia publica: <https://support.chess.com/en/articles/8572705-how-are-moves-classified-what-is-a-blunder-or-brilliant-etc>

## Estado atual

Entregas 0, 1 e 2 concluidas, mais a interface web local (partida contra o motor
e tabuleiro de analise). A classificacao de jogadas brilhantes chega nas
proximas entregas; os comandos correspondentes falham de forma explicita com
codigo de saida 3 em vez de imprimir resultado plausivel.

| Comando | Estado |
| --- | --- |
| `brilliant-chess doctor` | funcionando, com handshake UCI real |
| `brilliant-chess serve` | funcionando (jogo + analise no navegador) |
| `brilliant-chess analyze-position` | Entrega 5 |
| `brilliant-chess classify-move` | Entrega 5 |
| `brilliant-chess choose-move` | Entrega 6 |
| `brilliant-chess analyze-pgn` | Entrega 7 |
| `brilliant-chess explain` | Entrega 7 |

## Requisitos

- Python 3.12 ou superior
- [uv](https://docs.astral.sh/uv/) para dependencias e lockfile
- Stockfish 18 ou versao estavel fixada (nao acompanha o repositorio)

## Instalacao

```bash
uv sync
```

O Stockfish nao acompanha o repositorio e nao e baixado sozinho. Tres formas de
apontar o executavel, nesta ordem de precedencia:

1. variavel de ambiente `BRILLIANT_CHESS_STOCKFISH`;
2. `engine.binary_path` em `config/strict_v1.yaml`;
3. qualquer executavel em `engines/` (diretorio local, fora do controle de
   versao) ou no `PATH`.

O script abaixo explica como instalar e, se voce informar `--url`, `--sha256` e
`--yes`, baixa e verifica o hash:

```bash
uv run python scripts/download_stockfish.py
```

Confira tudo com:

```bash
uv run brilliant-chess doctor
```

## Interface local

```bash
uv run brilliant-chess serve
```

Abre em <http://127.0.0.1:8000>:

- **/jogar** — partida completa contra o Stockfish, com forca de ~1320 Elo ate
  sem limite, arrastar ou clicar para mover, promocao, desfazer, girar o
  tabuleiro e exportar a partida atual em PGN;
- **/analise** — cole uma FEN ou mova as pecas e veja as melhores jogadas com
  setas coloridas, avaliacao, variantes e a lista de linhas;
- **/docs** — documentacao automatica da API.

O servidor escuta apenas em loopback por padrao. Usar outro endereco imprime um
aviso de fair play.

## Uso pela CLI

```bash
uv run brilliant-chess doctor --format json
```

## Desenvolvimento

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run mypy src
```

Testes de integracao com o motor real:

```bash
uv run pytest -m slow
```

## Documentacao

- [`AGENTS.md`](AGENTS.md) — instrucoes operacionais para agentes e pessoas
- [`docs/architecture.md`](docs/architecture.md) — fronteiras e dependencias
- [`docs/domain-rules.md`](docs/domain-rules.md) — especificacao normativa das regras
- [`docs/calibration.md`](docs/calibration.md) — dataset, metricas e limiares
- [`docs/data-model.md`](docs/data-model.md) — persistencia e chave de cache
- [`docs/testing.md`](docs/testing.md) — estrategia de testes
- [`docs/decisions/`](docs/decisions/) — ADRs, incluindo a
  [0005](docs/decisions/0005-local-web-interface.md) sobre a interface local e
  seus limites de fair play

## Licenca

GNU GPL v3 ou posterior. Ver [`LICENSE`](LICENSE) e
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
