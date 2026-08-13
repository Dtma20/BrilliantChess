# AGENTS.md

Instrucoes operacionais para qualquer agente ou pessoa que trabalhe neste repositorio.

## Objetivo

Classificar e selecionar jogadas "brilhantes" com Stockfish para busca e regras
deterministicas para decisao. Toda decisao precisa ser explicavel: valores
medidos, limiares, portoes aprovados e reprovados, linhas principais e versoes.

## Comandos

Atalhos no `Makefile`: `make` lista tudo, `make install` prepara o ambiente,
`make run` constroi a interface e sobe o servidor, `make dev` roda Vite e API
lado a lado, `make check` passa lint, tipos e testes dos dois lados. Os comandos
diretos continuam valendo.

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check .
```

```bash
uv run mypy src
```

```bash
uv run brilliant-chess doctor
```

```bash
uv run brilliant-chess serve
```

Interface web (React + TypeScript + Vite), a partir de `frontend/`:

```bash
npm install
```

```bash
npm run build
```

```bash
npm run dev
```

```bash
npm test
```

```bash
npm run typecheck
```

`serve` entrega o que estiver em `frontend/dist`. Sem build, ele responde com
uma pagina explicando como gerar. Em desenvolvimento, use `npm run dev` em
`127.0.0.1:5173`, que faz proxy de `/api` para o FastAPI.

Testes de integracao com motor real: `uv run pytest -m slow` (pulam sozinhos se
o Stockfish nao estiver instalado).

## Mapa dos modulos

| Caminho | Responsabilidade |
| --- | --- |
| `domain/values.py` | Enums, codigos de motivo e constantes |
| `domain/errors.py` | Hierarquia de erros |
| `domain/models.py` | Posicao, jogada, orcamento, identidade, avaliacao, PV |
| `domain/expected_points.py` | WDL/centipawn/mate para pontos esperados e perda |
| `domain/material.py` | Valores materiais e aritmetica sobre snapshots |
| `domain/sacrifice.py` | Evidencia de sacrificio e confianca |
| `domain/rule_set.py` | Limiares configuraveis como tipos puros |
| `domain/gates.py` | Portoes obrigatorios de `strict_v1` |
| `domain/scoring.py` | Componentes de pontuacao e decisao final |
| `domain/strength.py` | Niveis de forca do motor para partidas locais |
| `ports/` | Contratos de motor, tabuleiro, repositorio e fonte de partidas |
| `application/` | Casos de uso: `diagnose`, `analyze_position`, `play_game` |
| `adapters/stockfish/` | Cliente UCI, mapeamento e localizacao do binario |
| `adapters/board/` | Regras de tabuleiro com python-chess |
| `interfaces/cli/` | Comandos e renderizacao |
| `interfaces/web/` | API local, sessao do motor e entrega do SPA |
| `frontend/src/lib/` | Cliente tipado da API e utilidades de tabuleiro |
| `frontend/src/components/` | Tabuleiro, shell e pecas do laboratorio |
| `frontend/src/pages/` | Inicio, jogar, analise e laboratorio |
| `bootstrap/` | Configuracao pydantic e montagem |

## Invariantes do dominio

1. `expected_points` sempre em `[0, 1]`.
2. Toda avaliacao e normalizada do ponto de vista de quem fez a candidata.
3. `expected_points_loss` nunca e negativa; ruido dentro da tolerancia vira zero
   e gera metadado.
4. Uma decisao brilhante exige **todos** os portoes obrigatorios aprovados.
5. `brilliance_score` nunca torna elegivel uma candidata reprovada.
6. Toda jogada e validada como legal antes de ir ao motor.
7. FEN invalida e PGN corrompido geram erro de dominio explicito.
8. Scores de mate ocupam faixa reservada de EP e nunca viram centipawns.
9. `domain/` nao importa CLI, banco, subprocesso, pydantic nem `python-chess`.
10. Orcamento por tempo nunca entra em golden tests; use nos.

## Quando uma regra mudar

Atualize, na mesma mudanca:

- `docs/domain-rules.md` (identificador, limiar, exemplos, historico);
- `config/strict_v1.yaml`;
- `domain/rule_set.py` e `bootstrap/config.py`;
- testes unitarios do portao;
- uma ADR em `docs/decisions/` se a definicao de brilhante mudar.

## Proibicoes

- **Nunca** implemente integracao com partidas ao vivo de terceiros: leitura de
  tela, captura de tabuleiro externo, automacao de cliques fora deste app,
  overlays ou conexao com partida em andamento em qualquer plataforma. A
  partida em tempo real permitida e a que acontece no tabuleiro deste projeto,
  contra o proprio motor.
- Nunca remova o aviso de fair play das paginas nem o padrao de escuta em
  loopback do `serve`.
- Nunca faca scraping do Game Review do Chess.com nem chame a plataforma
  repetidamente para obter rotulos privados.
- Nunca altere golden fixtures apenas para fazer testes passarem. Se a
  expectativa estiver errada, justifique por escrito e registre a mudanca.
- Nunca desabilite testes, lint ou tipagem para "terminar".
- Nunca apresente o resultado como equivalente ao do Chess.com.

## Definicao de pronto de uma entrega

- Testes relevantes passam (`pytest`).
- `ruff check`, `ruff format --check` e `mypy src` limpos.
- Documentacao afetada atualizada.
- Arquivos alterados listados, riscos e proximo passo informados.
- Nenhum segredo, caminho pessoal ou binario grande commitado.
- `frontend/dist` e `node_modules` fora do versionamento.
- Cobertura do dominio >= 90% e global >= 80%.

## Estado por entrega

- Entrega 0 (scaffold, `doctor`): concluida.
- Entrega 1 (dominio puro, ports, motor falso): concluida.
- Entrega 2 (adapter Stockfish, handshake no `doctor`): concluida.
- Entrega 3 (discovery + confirmation, EP loss): parcial — falta o estagio de
  estabilidade e o cache persistente.
- Interface web local (jogo + analise): concluida, ver ADR 0005.
- Laboratorio de duelo entre motores: interface concluida.
- Migracao do front para React + Vite + Tailwind: concluida, ver ADR 0006.
- Entrega 4 (detector de sacrificio): proxima.
- Entregas 5 a 9: pendentes, ver especificacao do projeto.
