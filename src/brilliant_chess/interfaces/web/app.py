"""Fabrica da aplicacao web local.

Fair play: este servidor e um app de estudo. Ele desenha o proprio tabuleiro e
nao le tela, nao controla mouse, nao cria overlay e nao conversa com nenhuma
plataforma de xadrez. O host padrao e loopback.

A interface e um SPA em React construido em ``frontend/``. Este modulo apenas
serve os arquivos estaticos do build e devolve ``index.html`` para as rotas de
navegacao; toda a logica continua na API.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.adapters.openings.suite import load_opening_suite
from brilliant_chess.application.opening_exploration import OpeningSelector
from brilliant_chess.bootstrap.container import Container, build_container
from brilliant_chess.interfaces.web.engine_pair_session import EnginePairSession
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from brilliant_chess.interfaces.web.match_store import MatchStore
from brilliant_chess.interfaces.web.opening_session import OpeningSession
from brilliant_chess.interfaces.web.routes import router

WEB_DIST_ENV_VAR = "BRILLIANT_CHESS_WEB_DIST"

#: Locais onde o build da interface pode estar, em ordem de preferencia.
_PACKAGE_DIST = Path(__file__).parent / "static"
_REPO_DIST = Path(__file__).resolve().parents[4] / "frontend" / "dist"

_BUILD_HINT = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8" />
<title>Brilliant Chess</title>
<style>
 body{background:#121311;color:#e9ece4;font:15px/1.6 system-ui,sans-serif}
 body{margin:0;padding:3rem 1.5rem}
 main{max-width:52ch;margin:0 auto}
 code{font-family:ui-monospace,monospace;color:#c9a227}
 p{color:#b3b9ab}
</style></head><body><main>
<h1>Interface ainda nao construida</h1>
<p>A API local ja esta no ar em <code>/api</code> e a documentacao em <code>/docs</code>.
Para ver a interface, construa o front uma vez:</p>
<p><code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code></p>
<p>Durante o desenvolvimento, use <code>npm run dev</code> e abra
<code>http://127.0.0.1:5173</code>; o proxy do Vite fala com este servidor.</p>
</main></body></html>
"""


def resolve_web_dist() -> Path | None:
    """Encontra o build da interface, ou ``None`` quando ele ainda nao existe."""
    override = os.environ.get(WEB_DIST_ENV_VAR)
    candidates = [Path(override)] if override else [_PACKAGE_DIST, _REPO_DIST]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


def _safe_asset(dist: Path, relative: str) -> Path | None:
    """Arquivo do build correspondente ao caminho, sem escapar do diretorio."""
    if not relative:
        return None
    candidate = (dist / relative).resolve()
    if not candidate.is_relative_to(dist.resolve()) or not candidate.is_file():
        return None
    return candidate


def create_app(container: Container | None = None) -> FastAPI:
    resolved = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            session: EngineSession = app.state.engine_session
            pair_session: EnginePairSession = app.state.engine_pair_session
            failure: BaseException | None = None
            for resource in (session, pair_session):
                try:
                    resource.close()
                except BaseException as exc:
                    if failure is None:
                        failure = exc
            if failure is not None:
                raise failure

    app = FastAPI(
        title="Brilliant Chess",
        description="Partida local contra o motor e tabuleiro de analise offline.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = resolved
    app.state.board = PythonChessBoardService()
    app.state.games = GameStore()
    app.state.matches = MatchStore()
    app.state.opening_session = OpeningSession()
    try:
        suite = load_opening_suite()
    except Exception:
        suite = ()
    app.state.opening_selector = OpeningSelector(suite, app.state.board)
    app.state.engine_session = EngineSession(resolved.settings)
    app.state.engine_pair_session = EnginePairSession(resolved.settings)
    app.include_router(router)

    dist = resolve_web_dist()
    app.state.web_dist = dist
    if dist is not None and (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    def spa(full_path: str) -> FileResponse | HTMLResponse:
        """Entrega o SPA. Rotas de navegacao sao resolvidas no navegador."""
        if full_path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Rota desconhecida")
        if dist is None:
            return HTMLResponse(_BUILD_HINT)
        asset = _safe_asset(dist, full_path)
        if asset is not None:
            return FileResponse(asset)
        # Um caminho com extensao e pedido de arquivo, nao de tela: devolver o
        # index.html ali so esconderia um 404 atras de HTML.
        if Path(full_path).suffix:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Arquivo nao encontrado")
        return FileResponse(dist / "index.html")

    return app
