# Exportação de partidas em PGN — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir baixar a partida local atual da tela /jogar como um arquivo PGN, durante ou depois da partida.

**Architecture:** A nova função build_pgn ficará em interfaces/web/pgn.py, recebendo apenas GameState e BoardView já produzidos pelos componentes existentes. A rota GET /api/game/{game_id}/pgn recuperará o estado em memória, gerará o PGN e responderá com Content-Disposition; o frontend terá apenas um botão que dispara o download dessa rota.

**Tech Stack:** Python 3.12, FastAPI/Starlette Response, Pydantic existente para contratos JSON, JavaScript ES modules sem dependências externas, pytest, Ruff e mypy.

## Global Constraints

- O app continua local e em loopback por padrão; não haverá integração com plataformas externas.
- domain/ não importará CLI, banco, subprocesso, pydantic nem python-chess.
- Nenhuma dependência nova será adicionada.
- O PGN será gerado a partir dos lances SAN já armazenados no GameState; não será feita reanálise pelo motor.
- A exportação será permitida durante a partida e após o término, mas o botão ficará desabilitado enquanto uma jogada estiver sendo processada.
- Partidas continuam voláteis em memória; persistência fica fora deste trabalho.

## File Map

- Create: src/brilliant_chess/interfaces/web/pgn.py — serialização determinística de GameState/BoardView para PGN.
- Create: tests/unit/test_pgn.py — testes puros de cabeçalhos, numeração, posição inicial preta, FEN personalizada e resultados.
- Modify: src/brilliant_chess/interfaces/web/routes.py — endpoint de download e resposta HTTP.
- Modify: tests/unit/test_web_api.py — contrato HTTP do download e erro para partida inexistente.
- Modify: src/brilliant_chess/interfaces/web/static/play.html — botão Exportar PGN.
- Modify: src/brilliant_chess/interfaces/web/static/play.js — habilitação do botão e disparo do download.
- Modify: README.md — documentar a exportação na lista de capacidades de /jogar.
- Modify: docs/decisions/0005-local-web-interface.md — registrar exportação sem alterar a decisão de não persistir.

---

### Task 1: Criar o serializador PGN puro

**Files:**
- Create: src/brilliant_chess/interfaces/web/pgn.py
- Test: tests/unit/test_pgn.py

**Interfaces:**
- Consumes: play_game.GameState, ports.board.BoardView, domain.values.Color e GameStatus.
- Produces: build_pgn(state, initial, current, *, standard_fen: str) -> str, retornando texto UTF-8 terminado por newline.

- [ ] **Step 1: Escrever os testes que falham**

Criar uma fixture PythonChessBoardService e um helper que constrói GameState
com moves_uci e moves_san derivados de board.view. Cobrir estes comportamentos:

~~~python
def test_build_pgn_has_headers_and_standard_movetext(board):
    state = state_with_moves(board, STARTING_FEN, Color.WHITE, ("e2e4", "e7e5"))
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Event "Brilliant Chess - Partida local"]' in pgn
    assert '[White "Voce"]' in pgn
    assert '[Black "Motor (Clube (~1900))"]' in pgn
    assert '[Result "*"]' in pgn
    assert "1. e4 e5 *" in pgn


def test_build_pgn_uses_black_ellipsis_for_black_to_move(board):
    state = state_with_moves(board, BLACK_TO_MOVE_FEN, Color.WHITE, ("e7e5",))
    initial = board.view(BLACK_TO_MOVE_FEN, ())
    current = board.view(BLACK_TO_MOVE_FEN, state.moves_uci)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert "1... e5 *" in pgn


def test_build_pgn_includes_setup_headers_for_custom_fen(board):
    custom_fen = "8/5k2/8/8/8/8/8/R5K1 b - - 0 12"
    state = state_with_moves(board, custom_fen, Color.WHITE, ())
    initial = board.view(custom_fen, ())
    current = initial

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[SetUp "1"]' in pgn
    assert f'[FEN "{custom_fen}"]' in pgn
    assert '[Result "*"]' in pgn


def test_build_pgn_maps_checkmate_to_result(board):
    moves = ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    state = state_with_moves(board, STARTING_FEN, Color.WHITE, moves)
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, moves)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Result "1-0"]' in pgn
    assert pgn.rstrip().endswith("1-0")
~~~

Adicionar também um caso de empate usando um status de empate produzido pelo
adapter, verificando que o resultado é 1/2-1/2.

- [ ] **Step 2: Rodar os testes para confirmar a falha**

~~~powershell
uv run pytest tests/unit/test_pgn.py -v
~~~

Esperado: falha porque o módulo pgn ainda não existe.

- [ ] **Step 3: Implementar o serializador mínimo**

Em pgn.py, implementar:

~~~python
def build_pgn(
    state: play_game.GameState,
    initial: BoardView,
    current: BoardView,
    *,
    standard_fen: str,
) -> str:
    ...
~~~

Regras exatas:

1. Calcular o resultado a partir de current.status e
   current.position.side_to_move: xeque-mate com o lado branco a jogar é 0-1;
   xeque-mate com o lado preto a jogar é 1-0; qualquer empate é 1/2-1/2;
   partida não terminada é *.
2. Definir Voce para a cor humana e Motor (<state.strength.label>) para a cor
   do motor.
3. Emitir Event, Site, White, Black e Result nesta ordem. Usar
   Brilliant Chess - Partida local e Localhost.
4. Se initial.position.fen != standard_fen, emitir também SetUp "1" e
   FEN "<initial.position.fen>".
5. Numerar a partir de initial.snapshot.fullmove_number e do lado indicado por
   initial.position.side_to_move. Para uma posição branca, usar 1. e4 e5; para
   uma posição preta, usar 1... e5. O número aumenta depois de cada lance preto.
6. Usar state.moves_san na ordem armazenada e acrescentar o token de resultado ao
   movetext. Escapar barra invertida e aspas nos valores dos cabeçalhos.

Não importar chess neste módulo: toda validação e normalização SAN já foram
feitas pelo BoardService.

- [ ] **Step 4: Rodar os testes para confirmar a passagem**

~~~powershell
uv run pytest tests/unit/test_pgn.py -v
uv run ruff check src/brilliant_chess/interfaces/web/pgn.py tests/unit/test_pgn.py
~~~

Esperado: todos os testes passam e o Ruff não reporta problemas.

- [ ] **Step 5: Commitar a unidade**

~~~powershell
git add src/brilliant_chess/interfaces/web/pgn.py tests/unit/test_pgn.py
git commit -m "feat: serialize local games as PGN"
~~~

### Task 2: Adicionar a rota HTTP de download

**Files:**
- Modify: src/brilliant_chess/interfaces/web/routes.py
- Test: tests/unit/test_web_api.py

**Interfaces:**
- Consumes: GameStore.get, PythonChessBoardService.view e build_pgn.
- Produces: GET /api/game/{game_id}/pgn, com 200, MIME
  application/x-chess-pgn e Content-Disposition:
  attachment; filename="brilliant-chess-<id>.pgn".

- [ ] **Step 1: Escrever os testes HTTP que falham**

Adicionar no teste web um helper que salva diretamente no GameStore um estado com
movimentos conhecidos, usando board.view para preencher moves_san. Adicionar:

~~~python
def test_game_pgn_download_returns_attachment(client):
    game = client.post("/api/game", json={"human_color": "white"}).json()

    response = client.get(f"/api/game/{game['game_id']}/pgn")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-chess-pgn"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="brilliant-chess-{game["game_id"]}.pgn"'
    )
    assert '[Result "*"]' in response.text


def test_game_pgn_download_reports_unknown_game(client):
    response = client.get("/api/game/naoexiste/pgn")

    assert response.status_code == 400
~~~

Também testar pela rota uma partida salva com a sequência de xeque-mate da Task 1
e uma partida iniciada com FEN personalizada, verificando 1-0 e SetUp/FEN no
corpo. Isso prova a integração entre armazenamento, adapter e serializador.

- [ ] **Step 2: Rodar os testes para confirmar a falha**

~~~powershell
uv run pytest tests/unit/test_web_api.py -k pgn -v
~~~

Esperado: falha porque a rota ainda não existe.

- [ ] **Step 3: Implementar a rota**

Importar Response de fastapi.responses e build_pgn. Adicionar:

~~~python
@router.get("/game/{game_id}/pgn")
def export_game_pgn(game_id: str, board: BoardDep, store: StoreDep) -> Response:
    with translated_errors():
        state = store.get(game_id)
        initial = board.view(state.initial_fen, ())
        current = play_game.current_view(board, state)
        pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)
        return Response(
            content=pgn,
            media_type="application/x-chess-pgn",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="brilliant-chess-{state.game_id}.pgn"'
                )
            },
        )
~~~

Manter a rota dentro de translated_errors() para que uma partida expirada ou
desconhecida continue seguindo o contrato HTTP existente (400).

- [ ] **Step 4: Rodar os testes para confirmar a passagem**

~~~powershell
uv run pytest tests/unit/test_web_api.py -k pgn -v
uv run pytest tests/unit/test_web_api.py -v
~~~

Esperado: os novos testes e todos os testes web passam.

- [ ] **Step 5: Commitar o endpoint**

~~~powershell
git add src/brilliant_chess/interfaces/web/routes.py tests/unit/test_web_api.py
git commit -m "feat: expose PGN download endpoint"
~~~

### Task 3: Adicionar o botão na tela Jogar

**Files:**
- Modify: src/brilliant_chess/interfaces/web/static/play.html
- Modify: src/brilliant_chess/interfaces/web/static/play.js

**Interfaces:**
- Consumes: game.game_id, o estado busy e o endpoint da Task 2.
- Produces: botão visual Exportar PGN, habilitado com uma partida carregada e
  desabilitado sem partida ou durante processamento.

- [ ] **Step 1: Alterar o HTML**

Adicionar ao grupo de controles da partida:

~~~html
<button id="export-pgn" type="button" disabled>Exportar PGN</button>
~~~

- [ ] **Step 2: Implementar o disparo de download**

Em play.js, registrar exportPgn em elements, alterar setBusy para atribuir
elements.exportPgn.disabled = value || !game, e adicionar:

~~~javascript
function exportPgn() {
  if (!game || busy) return;
  const link = document.createElement("a");
  link.href = \`/api/game/\${encodeURIComponent(game.game_id)}/pgn\`;
  link.download = \`brilliant-chess-\${game.game_id}.pgn\`;
  document.body.append(link);
  link.click();
  link.remove();
}

elements.exportPgn.addEventListener("click", exportPgn);
~~~

O download deve continuar disponível quando game.board.status deixar de ser
in_progress; somente busy e ausência de partida o desabilitam.

- [ ] **Step 3: Verificar a tela servida**

~~~powershell
uv run pytest tests/unit/test_web_api.py::test_pages_are_served -v
uv run ruff check src/brilliant_chess/interfaces/web/static
~~~

Como não há harness JavaScript no projeto, confirmar também manualmente em uma
execução local: iniciar uma partida, fazer pelo menos um lance, clicar em
Exportar PGN e verificar que o navegador salva um arquivo .pgn com os lances
exibidos.

- [ ] **Step 4: Commitar a interface**

~~~powershell
git add src/brilliant_chess/interfaces/web/static/play.html src/brilliant_chess/interfaces/web/static/play.js
git commit -m "feat: add PGN export button"
~~~

### Task 4: Atualizar documentação e executar a verificação completa

**Files:**
- Modify: README.md
- Modify: docs/decisions/0005-local-web-interface.md

**Interfaces:**
- Consumes: comportamento implementado nas Tasks 1–3.
- Produces: documentação pública que menciona a exportação e decisão
  arquitetural que mantém partidas somente em memória.

- [ ] **Step 1: Atualizar o README**

Na descrição de /jogar, acrescentar que a tela permite desfazer, girar o
tabuleiro e exportar a partida atual em PGN.

- [ ] **Step 2: Atualizar a ADR 0005**

Nas consequências, acrescentar que o estado volátil de uma partida pode ser
baixado como PGN pela interface, mas o arquivo é uma exportação explícita e não
substitui a persistência prevista para a Entrega 7.

- [ ] **Step 3: Rodar a suíte completa e as verificações estáticas**

~~~powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
~~~

Esperado: todos os testes passam, Ruff não encontra erros, o formato está limpo
e mypy termina sem erros.

- [ ] **Step 4: Revisar o diff final e o estado do git**

~~~powershell
git diff --check
git status --short
git log --oneline -5
~~~

Confirmar que não há arquivos gerados, segredos ou binários adicionados e que os
únicos arquivos desta entrega são os listados no mapa do plano.

- [ ] **Step 5: Commitar documentação e verificação**

~~~powershell
git add README.md docs/decisions/0005-local-web-interface.md
git commit -m "docs: document PGN export"
~~~
