# Avisos de terceiros

Este documento registra dependencias e licencas. Nao substitui analise juridica.

## Motor externo

| Componente | Licenca | Observacao |
| --- | --- | --- |
| Stockfish | GNU GPL v3 | Nao acompanha o repositorio nem o controle de versao. Instalado localmente em `engines/` (ignorado pelo git) e executado como processo externo via UCI. A copia local inclui `Copying.txt` e `AUTHORS` do proprio projeto Stockfish. |
| Redes NNUE do Stockfish | ver projeto Stockfish | Distribuidas com o motor; nao sao versionadas aqui. |

## Dependencias Python

| Pacote | Licenca declarada | Uso |
| --- | --- | --- |
| `chess` (python-chess) | GNU GPL v3 | FEN, PGN, legalidade e comunicacao UCI (apenas em adapters) |
| `pydantic` | MIT | Validacao de configuracao e modelos de fronteira |
| `typer` | MIT | CLI |
| `rich` | MIT | Saida humana |
| `pyyaml` | MIT | Leitura de configuracao |
| `structlog` | MIT ou Apache-2.0 (dupla) | Logging estruturado |
| `fastapi` | MIT | API da interface web local |
| `starlette` | BSD-3-Clause | Base HTTP do FastAPI |
| `uvicorn` | BSD-3-Clause | Servidor ASGI local |

O tabuleiro do navegador e escrito neste repositorio em JavaScript e SVG, sem
biblioteca de terceiros. As pecas usam glifos Unicode, nao imagens licenciadas.

Ferramentas de desenvolvimento (`pytest`, `pytest-cov`, `hypothesis`, `httpx`,
`ruff`, `mypy`, `types-pyyaml`) nao sao redistribuidas com o projeto.

## Consequencia da GPL

`python-chess` e o Stockfish sao GPL v3. Por isso este projeto e licenciado como
**GNU GPL v3 ou posterior** (ver `LICENSE` e
`docs/decisions/0003-gpl-compatible-licensing.md`). Ao redistribuir:

- preserve avisos de copyright e de licenca;
- disponibilize o codigo-fonte correspondente;
- anexe o texto completo da GPL v3 em `LICENSE` (pendencia registrada no
  proprio arquivo).

## Dados publicos

Nenhum dado do Chess.com e importado no MVP. Quando a Entrega 9 for autorizada,
cada importacao deve registrar origem e termos no campo `provenance` de
`ports/game_source.py`.
