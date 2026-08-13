"""Rotas da interface web local."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application import play_game, play_match
from brilliant_chess.application.analyze_position import (
    AnalysisRequest,
    PositionAnalysis,
    analyze_position,
)
from brilliant_chess.application.choose_brilliant_move import choose_brilliant_move
from brilliant_chess.application.play_match import (
    MatchAudit,
    MatchProfile,
    MatchState,
    SelectionKind,
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
from brilliant_chess.domain.values import Color
from brilliant_chess.interfaces.web.engine_pair_session import EnginePairSession
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from brilliant_chess.interfaces.web.match_store import MatchStore
from brilliant_chess.interfaces.web.pgn import build_pgn
from brilliant_chess.interfaces.web.schemas import (
    AnalysisOut,
    AnalyzeIn,
    ArrowOut,
    BoardIn,
    BoardOut,
    CandidateAuditOut,
    GameOut,
    MatchMoveOut,
    MatchOut,
    MatchProfileOut,
    MoveIn,
    NewGameIn,
    NewMatchIn,
    StrengthOut,
    analysis_out,
    board_out,
    evaluation_text,
    gate_out,
)
from brilliant_chess.ports.engine import ChessEngine, PlayableEngine

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


def get_match_store(request: Request) -> MatchStore:
    store: MatchStore = request.app.state.matches
    return store


def get_pair_session(request: Request) -> EnginePairSession:
    pair: EnginePairSession = request.app.state.engine_pair_session
    return pair


BoardDep = Annotated[PythonChessBoardService, Depends(get_board)]
StoreDep = Annotated[GameStore, Depends(get_store)]
SessionDep = Annotated[EngineSession, Depends(get_session)]
MatchStoreDep = Annotated[MatchStore, Depends(get_match_store)]
PairSessionDep = Annotated[EnginePairSession, Depends(get_pair_session)]


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


@router.post("/match", status_code=status.HTTP_201_CREATED)
def create_match(
    payload: NewMatchIn, request: Request, board: BoardDep, store: MatchStoreDep
) -> MatchOut:
    with translated_errors():
        initial_fen = payload.initial_fen or STARTING_FEN
        board.view(initial_fen, ())
        lab = request.app.state.container.settings.web.lab
        state = play_match.start_match(
            match_id=store.new_id(),
            initial_fen=initial_fen,
            white=MatchProfile(payload.white.strength_key, payload.white.policy),
            black=MatchProfile(payload.black.strength_key, payload.black.policy),
            max_plies=lab.max_fullmoves * 2,
        )
        return match_out(board, store.save(state))


@router.get("/match/{match_id}")
def read_match(match_id: str, board: BoardDep, store: MatchStoreDep) -> MatchOut:
    with translated_errors():
        return match_out(board, store.get(match_id))


@router.post("/match/{match_id}/step")
def step_match(
    match_id: str,
    request: Request,
    board: BoardDep,
    store: MatchStoreDep,
    pair: PairSessionDep,
) -> MatchOut:
    with translated_errors():
        state = store.get(match_id)
        view = play_match.current_view(board, state)
        if not play_match.can_step(board, state):
            raise DomainError("Partida encerrada")
        profile, engine = _profile_and_engine(state, view.position.side_to_move, pair)
        rules = request.app.state.container.rules
        lab = request.app.state.container.settings.web.lab
        choice = (
            choose_brilliant_move(engine, board, view.position, rules, lab.strict_budget())
            if profile.policy is play_match.MatchPolicy.STRICT_V1
            else None
        )
        selected = choice.selected if choice is not None else None
        move = (
            choice.move
            if choice is not None and choice.move is not None
            else cast(PlayableEngine, engine).play_move(
                view.position, strength_by_key(profile.strength_key)
            )
        )
        selection = (
            SelectionKind.STRICT_V1
            if choice is not None and choice.move is not None
            else (
                SelectionKind.FALLBACK
                if profile.policy is play_match.MatchPolicy.STRICT_V1
                else SelectionKind.NORMAL
            )
        )
        audit = (
            MatchAudit(selected.decision, selected.best_defense_uci, selected.stability_depth)
            if selected is not None and choice is not None and choice.move is not None
            else None
        )
        return match_out(
            board, store.save(play_match.record_move(board, state, move, selection, audit))
        )


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


def _profile_and_engine(
    state: MatchState, color: Color, pair: EnginePairSession
) -> tuple[MatchProfile, ChessEngine]:
    return (
        (state.white, pair.white_engine())
        if color is Color.WHITE
        else (state.black, pair.black_engine())
    )


def match_out(board: PythonChessBoardService, state: MatchState) -> MatchOut:
    view = play_match.current_view(board, state)
    return MatchOut(
        match_id=state.match_id,
        white=_match_profile_out(state.white),
        black=_match_profile_out(state.black),
        board=board_out(view),
        moves_uci=list(state.moves_uci),
        moves_san=list(state.moves_san),
        moves=[_match_move_out(move) for move in state.moves],
        result_text=play_match.result_text(board, state),
        can_step=play_match.can_step(board, state),
    )


def _match_profile_out(profile: MatchProfile) -> MatchProfileOut:
    level = strength_by_key(profile.strength_key)
    return MatchProfileOut(
        strength=StrengthOut(key=level.key, label=level.label, elo=level.elo),
        policy=profile.policy,
    )


def _match_move_out(move: play_match.MatchMove) -> MatchMoveOut:
    return MatchMoveOut(
        color=move.color,
        uci=move.uci,
        san=move.san,
        selection=move.selection,
        fallback=move.selection is SelectionKind.FALLBACK,
        audit=None if move.audit is None else _audit_out(move),
    )


def _audit_out(move: play_match.MatchMove) -> CandidateAuditOut:
    assert move.audit is not None
    decision = move.audit.decision
    return CandidateAuditOut(
        selected_uci=move.uci,
        selected_san=move.san,
        score=decision.score,
        rule_set_version=decision.rule_set_version,
        gates=[gate_out(gate) for gate in decision.gates],
        reason_codes=list(decision.reasons),
    )
