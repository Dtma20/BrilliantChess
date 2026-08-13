"""Rotas da interface web local."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application import play_game
from brilliant_chess.application.analyze_position import (
    AnalysisRequest,
    PositionAnalysis,
    analyze_position,
)
from brilliant_chess.domain.errors import (
    BrilliantChessError,
    DomainError,
    EngineError,
    IllegalMoveError,
    InvalidFenError,
    InvalidMoveError,
)
from brilliant_chess.domain.models import AnalysisBudget, Position
from brilliant_chess.domain.strength import STRENGTH_LEVELS, strength_by_key
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from brilliant_chess.interfaces.web.pgn import build_pgn
from brilliant_chess.interfaces.web.schemas import (
    AnalysisOut,
    AnalyzeIn,
    ArrowOut,
    BoardIn,
    BoardOut,
    GameOut,
    MoveIn,
    NewGameIn,
    StrengthOut,
    analysis_out,
    board_out,
    evaluation_text,
)

router = APIRouter(prefix="/api")

#: Cor por rank da candidata. Verde e a melhor, como em tabuleiros conhecidos.
ARROW_COLORS = ("#3fb950", "#4c8dff", "#d29922", "#8b949e")

_BAD_REQUEST = (InvalidFenError, InvalidMoveError, IllegalMoveError, DomainError)


def get_board(request: Request) -> PythonChessBoardService:
    board: PythonChessBoardService = request.app.state.board
    return board


def get_store(request: Request) -> GameStore:
    store: GameStore = request.app.state.games
    return store


def get_session(request: Request) -> EngineSession:
    session: EngineSession = request.app.state.engine_session
    return session


BoardDep = Annotated[PythonChessBoardService, Depends(get_board)]
StoreDep = Annotated[GameStore, Depends(get_store)]
SessionDep = Annotated[EngineSession, Depends(get_session)]


@contextmanager
def translated_errors() -> Iterator[None]:
    """Converte erros de dominio em respostas HTTP, sem vazar stack trace."""
    try:
        yield
    except _BAD_REQUEST as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except BrilliantChessError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc


@router.get("/health")
def health(request: Request, session: SessionDep) -> dict[str, object]:
    binary = session.binary_path
    return {
        "status": "ok",
        "engine_binary": str(binary) if binary else None,
        "rule_set": request.app.state.container.rules.id,
    }


@router.get("/strengths")
def strengths() -> list[StrengthOut]:
    return [
        StrengthOut(key=level.key, label=level.label, elo=level.elo) for level in STRENGTH_LEVELS
    ]


@router.post("/game", status_code=status.HTTP_201_CREATED)
def create_game(
    payload: NewGameIn, board: BoardDep, store: StoreDep, session: SessionDep
) -> GameOut:
    with translated_errors():
        state = play_game.start_game(
            game_id=store.new_id(),
            initial_fen=payload.initial_fen or STARTING_FEN,
            human_color=payload.human_color,
            strength_key=payload.strength_key,
        )
        board.view(state.initial_fen, ())
        if play_game.is_engine_turn(board, state):
            state = play_game.play_engine_move(board, session.engine(), state)
        return _game_out(board, store.save(state))


@router.get("/game/{game_id}")
def read_game(game_id: str, board: BoardDep, store: StoreDep) -> GameOut:
    with translated_errors():
        return _game_out(board, store.get(game_id))


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


@router.post("/game/{game_id}/move")
def make_move(
    game_id: str, payload: MoveIn, board: BoardDep, store: StoreDep, session: SessionDep
) -> GameOut:
    with translated_errors():
        state = play_game.play_human_move(board, store.get(game_id), payload.move)
        if play_game.is_engine_turn(board, state):
            state = play_game.play_engine_move(board, session.engine(), state)
        return _game_out(board, store.save(state))


@router.post("/game/{game_id}/undo")
def undo(game_id: str, board: BoardDep, store: StoreDep) -> GameOut:
    with translated_errors():
        state = play_game.undo_full_move(board, store.get(game_id))
        return _game_out(board, store.save(state))


@router.post("/board")
def board_state(payload: BoardIn, board: BoardDep) -> BoardOut:
    """Aplica lances a uma FEN e devolve a posicao resultante e os lances legais."""
    with translated_errors():
        return board_out(board.view(payload.fen or STARTING_FEN, payload.moves))


@router.post("/analyze")
def analyze(
    payload: AnalyzeIn, request: Request, board: BoardDep, session: SessionDep
) -> AnalysisOut:
    web = request.app.state.container.settings.web
    with translated_errors():
        position = Position.from_fen(payload.fen)
        view = board.view(position.fen, ())
        engine = session.engine()
        if view.status.is_finished or not view.legal_moves:
            empty = PositionAnalysis(
                position=position,
                side_to_move=position.side_to_move,
                engine=engine.identity(),
                expected_points_before=0.0,
                candidates=(),
                warnings=(),
            )
            return analysis_out(empty, view, [])
        breadth = payload.multipv or web.analysis_multipv
        analysis = analyze_position(
            engine,
            board,
            AnalysisRequest(
                position=position,
                discovery_budget=AnalysisBudget(
                    nodes=payload.discovery_nodes or web.analysis_discovery_nodes
                ),
                confirmation_budget=AnalysisBudget(
                    nodes=payload.confirmation_nodes or web.analysis_confirmation_nodes
                ),
                multipv=breadth,
                max_candidates=breadth,
            ),
        )
        return analysis_out(analysis, view, _arrows(analysis, web.max_arrows))


def _arrows(analysis: PositionAnalysis, max_arrows: int) -> list[ArrowOut]:
    return [
        ArrowOut(
            from_square=candidate.move_uci[:2],
            to_square=candidate.move_uci[2:4],
            rank=candidate.rank,
            color=ARROW_COLORS[min(candidate.rank - 1, len(ARROW_COLORS) - 1)],
            label=f"{candidate.move_san} {evaluation_text(candidate)}",
        )
        for candidate in analysis.candidates[:max_arrows]
    ]


def _game_out(board: PythonChessBoardService, state: play_game.GameState) -> GameOut:
    view = play_game.current_view(board, state)
    level = strength_by_key(state.strength_key)
    return GameOut(
        game_id=state.game_id,
        human_color=state.human_color,
        strength=StrengthOut(key=level.key, label=level.label, elo=level.elo),
        board=board_out(view),
        moves_san=list(state.moves_san),
        moves_uci=list(state.moves_uci),
        engine_thinking=play_game.is_engine_turn(board, state),
        result_text=play_game.result_text(
            view.status, view.position.side_to_move, state.human_color
        ),
    )
