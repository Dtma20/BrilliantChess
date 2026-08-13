"""Fabrica da aplicacao web local.

Fair play: este servidor e um app de estudo. Ele desenha o proprio tabuleiro e
nao le tela, nao controla mouse, nao cria overlay e nao conversa com nenhuma
plataforma de xadrez. O host padrao e loopback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.bootstrap.container import Container, build_container
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from brilliant_chess.interfaces.web.routes import router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(container: Container | None = None) -> FastAPI:
    resolved = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            session: EngineSession = app.state.engine_session
            session.close()

    app = FastAPI(
        title="Brilliant Chess",
        description="Partida local contra o motor e tabuleiro de analise offline.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = resolved
    app.state.board = PythonChessBoardService()
    app.state.games = GameStore()
    app.state.engine_session = EngineSession(resolved.settings)
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/jogar", include_in_schema=False)
    def play_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "play.html")

    @app.get("/analise", include_in_schema=False)
    def analysis_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "analysis.html")

    return app
