"""Rotas da interface web local."""

from __future__ import annotations

import random
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.adapters.game_source.pgn import parse_pgn
from brilliant_chess.application import play_game, play_match
from brilliant_chess.application.analyze_position import (
    AnalysisRequest,
    PositionAnalysis,
    analyze_position,
)
from brilliant_chess.application.choose_brilliant_move import (
    CandidateAudit,
    PositionHistory,
    choose_brilliant_move,
)
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
    GameSourceError,
    IllegalMoveError,
    InvalidFenError,
    InvalidMoveError,
)
from brilliant_chess.domain.models import AnalysisBudget, Move, Position
from brilliant_chess.domain.opening import (
    OpeningConfig,
    OpeningExitReason,
    OpeningIdentity,
    OpeningMode,
    OpeningMoveAudit,
    OpeningPhaseState,
)
from brilliant_chess.domain.strength import STRENGTH_LEVELS, strength_by_key
from brilliant_chess.domain.values import Color
from brilliant_chess.interfaces.web.engine_pair_session import EnginePairSession
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from brilliant_chess.interfaces.web.match_store import MatchStore
from brilliant_chess.interfaces.web.pgn import build_match_pgn, build_pgn
from brilliant_chess.interfaces.web.schemas import (
    AnalysisOut,
    AnalyzeIn,
    ArrowOut,
    BoardIn,
    BoardOut,
    CandidateAuditOut,
    GameOut,
    LabOut,
    MatchMoveOut,
    MatchOut,
    MatchProfileOut,
    MoveIn,
    NewGameIn,
    NewMatchIn,
    PgnImportIn,
    PgnImportOut,
    StrengthOut,
    analysis_out,
    board_out,
    engine_identity_out,
    evaluation_text,
    exchange_out,
    gate_out,
    node_budgets_out,
    non_obviousness_out,
    opening_config_out,
    opening_identity_out,
    opening_move_audit_out,
    opening_phase_out,
    sacrifice_out,
)
from brilliant_chess.ports.board import BoardView
from brilliant_chess.ports.engine import ChessEngine, PlayableEngine

router = APIRouter(prefix="/api")

#: Cor por rank da candidata. Verde e a melhor, como em tabuleiros conhecidos.
ARROW_COLORS = ("#7fa96a", "#c9a227", "#949b8a", "#7f8579")

_BAD_REQUEST = (InvalidFenError, InvalidMoveError, IllegalMoveError, DomainError, GameSourceError)


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


@router.get("/lab")
def lab_settings(request: Request) -> LabOut:
    """Limite experimental e cadencia do autoplay, que roda no navegador."""
    lab = request.app.state.container.settings.web.lab
    return LabOut(
        max_fullmoves=lab.max_fullmoves,
        max_plies=lab.max_fullmoves * 2,
        autoplay_delay_ms=lab.autoplay_delay_ms,
        strict_policy=lab.strict_policy,
    )


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

        raw_mode = payload.opening.mode if payload.opening and payload.opening.mode else None
        if raw_mode is not None:
            try:
                mode = OpeningMode(raw_mode)
            except ValueError:
                mode = lab.opening.default_mode
        else:
            mode = lab.opening.default_mode

        provided_seed = payload.opening.seed if payload.opening else None
        seed = provided_seed if provided_seed is not None else secrets.randbits(32)

        opening_config = lab.opening.for_mode(mode, seed=seed)
        if payload.opening and payload.opening.line_id:
            opening_config = replace(opening_config, line_id=payload.opening.line_id)
        opening_identity = None
        opening_phase = None

        if mode is not OpeningMode.OFF:
            usage_snapshot = request.app.state.opening_session.usage_snapshot()
            line, planned_exit, reason = request.app.state.opening_selector.choose(
                initial_fen, opening_config, usage_counts=usage_snapshot
            )
            if line is not None:
                request.app.state.opening_session.record_usage(line.line_id)
                opening_identity = OpeningIdentity(
                    line_id=line.line_id,
                    family=line.family,
                    eco=line.eco,
                    name=line.name,
                    variation=line.variation,
                )
                opening_phase = OpeningPhaseState(
                    active=True,
                    mode=mode,
                    seed=seed,
                    planned_exit_ply=planned_exit,
                    completed_opening_plies=0,
                    current_phase="suite",
                    exit_reason=None,
                    selected_identity=opening_identity,
                )
            else:
                opening_phase = OpeningPhaseState(
                    active=False,
                    mode=mode,
                    seed=seed,
                    planned_exit_ply=0,
                    completed_opening_plies=0,
                    current_phase="ended",
                    exit_reason=reason or OpeningExitReason.NO_COMPATIBLE_LINE,
                    selected_identity=None,
                )
        else:
            opening_phase = None

        state = play_match.start_match(
            match_id=store.new_id(),
            initial_fen=initial_fen,
            white=MatchProfile(payload.white.strength_key, payload.white.policy),
            black=MatchProfile(payload.black.strength_key, payload.black.policy),
            max_plies=lab.max_fullmoves * 2,
            opening_config=opening_config,
            opening_seed=seed,
            opening_identity=opening_identity,
            opening_phase=opening_phase,
            opening_dataset_version="suite_v1",
            opening_usage_snapshot=request.app.state.opening_session.usage_snapshot(),
        )
        return match_out(board, store.save(state))


@router.get("/match/{match_id}")
def read_match(match_id: str, board: BoardDep, store: MatchStoreDep) -> MatchOut:
    with translated_errors():
        return match_out(board, store.get(match_id))


@router.get("/match/{match_id}/pgn")
def export_match_pgn(match_id: str, board: BoardDep, store: MatchStoreDep) -> Response:
    with translated_errors():
        state = store.get(match_id)
        initial = board.view(state.initial_fen, ())
        current = play_match.current_view(board, state)
        pgn = build_match_pgn(state, initial, current, standard_fen=STARTING_FEN)
        return Response(
            content=pgn,
            media_type="application/x-chess-pgn",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="brilliant-chess-match-{state.match_id}.pgn"'
                )
            },
        )


def _step_suite_phase(
    board: PythonChessBoardService,
    state: MatchState,
    view: BoardView,
    request: Request,
    cfg: OpeningConfig,
) -> MatchState:
    current_ply = len(state.moves_uci)
    identity = state.opening_phase.selected_identity if state.opening_phase else None
    matching_line = next(
        (
            line_item
            for line_item in request.app.state.opening_selector.lines
            if identity and line_item.line_id == identity.line_id
        ),
        None,
    )
    if (
        matching_line is not None
        and state.opening_phase is not None
        and current_ply < len(matching_line.moves_uci)
        and current_ply < state.opening_phase.planned_exit_ply
    ):
        move_uci = matching_line.moves_uci[current_ply]
        norm = board.normalize_move(view.position, move_uci)
        opening_audit = OpeningMoveAudit(
            opening_mode=state.opening_phase.mode,
            seed=state.opening_phase.seed,
            eco=matching_line.eco,
            name=matching_line.name,
            variation=matching_line.variation,
            source="suite",
            candidate_rank=1,
            candidate_ep_loss=0.0,
            sampling_weight=1.0,
            candidates_considered=(move_uci,),
            quality_cutoff=cfg.max_ep_loss,
            search_budget=AnalysisBudget(nodes=cfg.budget_nodes),
            opening_ply=current_ply + 1,
            planned_exit_ply=state.opening_phase.planned_exit_ply,
            sampling_mode=None,
            experimental=cfg.experimental,
        )
        next_ply = current_ply + 1
        if next_ply >= state.opening_phase.planned_exit_ply:
            if cfg.extra_plies > 0:
                new_phase = replace(
                    state.opening_phase,
                    completed_opening_plies=next_ply,
                    current_phase="multipv_sampling",
                )
            else:
                new_phase = replace(
                    state.opening_phase,
                    active=False,
                    completed_opening_plies=next_ply,
                    current_phase="ended",
                    exit_reason=OpeningExitReason.PLANNED_EXIT,
                )
        else:
            new_phase = replace(
                state.opening_phase,
                completed_opening_plies=next_ply,
            )
        return play_match.record_move(
            board,
            state,
            norm,
            SelectionKind.OPENING_EXPLORATION,
            audit=None,
            opening_audit=opening_audit,
            opening_phase=new_phase,
        )

    if state.opening_phase is None:
        return state

    if cfg.extra_plies > 0:
        return replace(
            state,
            opening_phase=replace(state.opening_phase, current_phase="multipv_sampling"),
        )
    return replace(
        state,
        opening_phase=replace(
            state.opening_phase,
            active=False,
            current_phase="ended",
            exit_reason=(
                OpeningExitReason.PLANNED_EXIT
                if current_ply >= state.opening_phase.planned_exit_ply
                else OpeningExitReason.LINE_EXHAUSTED
            ),
        ),
    )


def _step_multipv_phase(  # noqa: PLR0913
    board: PythonChessBoardService,
    state: MatchState,
    view: BoardView,
    request: Request,
    pair: EnginePairSession,
    *,
    cfg: OpeningConfig,
) -> MatchState:
    if state.opening_phase is None or not state.opening_phase.active:
        return state
    current_ply = len(state.moves_uci)
    total_target_plies = state.opening_phase.planned_exit_ply + cfg.extra_plies
    if current_ply >= total_target_plies:
        return state

    _profile, engine = _profile_and_engine(state, view.position.side_to_move, pair)
    rng = random.Random(state.opening_phase.seed + current_ply)
    identity = state.opening_phase.selected_identity
    move, opening_audit, exit_reason = request.app.state.opening_selector.sample_multipv_move(
        view.position,
        engine,
        cfg,
        rng,
        opening_ply=current_ply + 1,
        planned_exit_ply=total_target_plies,
        eco=identity.eco if identity else "",
        name=identity.name if identity else "",
        variation=identity.variation if identity else None,
    )
    if move is not None and opening_audit is not None:
        next_ply = current_ply + 1
        if next_ply >= total_target_plies:
            new_phase = replace(
                state.opening_phase,
                active=False,
                completed_opening_plies=next_ply,
                current_phase="ended",
                exit_reason=OpeningExitReason.PLANNED_EXIT,
            )
        else:
            new_phase = replace(
                state.opening_phase,
                completed_opening_plies=next_ply,
            )
        return play_match.record_move(
            board,
            state,
            move,
            SelectionKind.OPENING_EXPLORATION,
            audit=None,
            opening_audit=opening_audit,
            opening_phase=new_phase,
        )

    return replace(
        state,
        opening_phase=replace(
            state.opening_phase,
            active=False,
            current_phase="ended",
            exit_reason=exit_reason or OpeningExitReason.NO_ACCEPTABLE_CANDIDATE,
        ),
    )


def _step_opening_move(
    board: PythonChessBoardService,
    state: MatchState,
    view: BoardView,
    request: Request,
    pair: EnginePairSession,
) -> MatchState | None:
    if state.opening_phase is None or not state.opening_phase.active:
        return None
    if view.status.is_finished:
        ended_phase = replace(
            state.opening_phase,
            active=False,
            current_phase="ended",
            exit_reason=OpeningExitReason.TERMINAL_POSITION,
        )
        return replace(state, opening_phase=ended_phase)

    cfg = state.opening_config or request.app.state.container.settings.web.lab.opening.for_mode(
        OpeningMode.EXPLORATORY
    )

    initial_plies = len(state.moves_uci)
    if state.opening_phase.current_phase == "suite":
        state = _step_suite_phase(board, state, view, request, cfg)
        if len(state.moves_uci) > initial_plies:
            return state

    if (
        state.opening_phase is not None
        and state.opening_phase.active
        and state.opening_phase.current_phase == "multipv_sampling"
    ):
        return _step_multipv_phase(board, state, view, request, pair, cfg=cfg)

    return state


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

        if state.opening_phase is not None and state.opening_phase.active:
            opening_state = _step_opening_move(board, state, view, request, pair)
            if opening_state is not None:
                if len(opening_state.moves_uci) > len(state.moves_uci):
                    return match_out(board, store.save(opening_state))
                state = store.save(opening_state)
                view = play_match.current_view(board, state)
                if not play_match.can_step(board, state):
                    return match_out(board, state)

        profile, engine = _profile_and_engine(state, view.position.side_to_move, pair)
        is_strict = profile.policy in {
            play_match.MatchPolicy.STRICT_V1,
            play_match.MatchPolicy.STRICT_V2,
        }
        rules = (
            request.app.state.container.rule_set_for(profile.policy)
            if is_strict
            else request.app.state.container.rules
        )
        lab = request.app.state.container.settings.web.lab
        choice = (
            choose_brilliant_move(
                engine,
                board,
                # Sem o caminho ate aqui, nem o tabuleiro nem o motor veem
                # tripla repeticao ou a regra dos cinquenta lances.
                PositionHistory(state.initial_fen, state.moves_uci),
                rules,
                lab.strict_budget(),
            )
            if is_strict
            else None
        )
        strict_selected = choice.selected if choice is not None else None
        near_selected = choice.near_selected if choice is not None else None
        audit_selected = None
        if choice is not None and choice.move is not None and strict_selected is not None:
            move = choice.move
            selection = (
                SelectionKind.STRICT_V2
                if profile.policy is play_match.MatchPolicy.STRICT_V2
                else SelectionKind.STRICT_V1
            )
            audit_selected = strict_selected
        elif near_selected is not None:
            move = Move(near_selected.candidate.move_uci, near_selected.candidate.move_san)
            selection = SelectionKind.NEAR_BRILLIANT
            audit_selected = near_selected
        else:
            move = cast(PlayableEngine, engine).play_move(
                view.position, strength_by_key(profile.strength_key)
            )
            selection = SelectionKind.FALLBACK if is_strict else SelectionKind.NORMAL
        audit = None if audit_selected is None else _match_audit(audit_selected)
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


@router.post("/pgn/import")
def import_pgn(payload: PgnImportIn) -> PgnImportOut:
    """Valida um PGN e devolve a linha principal pronta para navegacao."""
    with translated_errors():
        parsed = parse_pgn(payload.pgn)
        return PgnImportOut(
            initial_fen=parsed.initial_fen,
            moves_uci=list(parsed.moves_uci),
            moves_san=list(parsed.moves_san),
        )


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
        initial_fen=state.initial_fen,
        white=_match_profile_out(state.white),
        black=_match_profile_out(state.black),
        board=board_out(view),
        moves_uci=list(state.moves_uci),
        moves_san=list(state.moves_san),
        moves=[_match_move_out(move) for move in state.moves],
        result_text=play_match.result_text(board, state),
        can_step=play_match.can_step(board, state),
        opening=opening_config_out(state.opening_config),
        opening_seed=state.opening_seed,
        opening_identity=opening_identity_out(state.opening_identity),
        opening_phase=opening_phase_out(state.opening_phase),
        opening_dataset_version=state.opening_dataset_version,
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
        audit=None if move.audit is None else _audit_out(move.audit, move.uci, move.san),
        opening_audit=opening_move_audit_out(move.opening_audit),
    )


def _match_audit(audited: CandidateAudit) -> MatchAudit:
    return MatchAudit(
        decision=audited.decision,
        best_defense_uci=audited.best_defense_uci,
        stability_depth=audited.stability_depth,
        best_defense_san=audited.best_defense_san,
        acceptance_san=audited.acceptance_san,
        defense_accepted=audited.defense_accepted,
        material_conceded=audited.material_conceded,
        terminal_status=audited.terminal_status,
        exchange=audited.exchange,
        non_obviousness=audited.non_obviousness,
        detector_version=audited.detector_version,
        engine_identity=audited.engine_identity,
        discovery_budget=audited.discovery_budget,
        confirmation_budget=audited.confirmation_budget,
        best_defense_budget=audited.best_defense_budget,
        stability_budget=audited.stability_budget,
        shallow_budget=audited.shallow_budget,
        shallow_multipv=audited.shallow_multipv,
    )


def _audit_out(audit: MatchAudit, uci: str, san: str) -> CandidateAuditOut:
    decision = audit.decision
    return CandidateAuditOut(
        selected_uci=uci,
        selected_san=san,
        score=decision.score,
        rule_set_version=decision.rule_set_version,
        gates=[gate_out(gate) for gate in decision.gates],
        reason_codes=list(decision.reasons),
        sacrifice=sacrifice_out(
            decision.sacrifice,
            acceptance_san=audit.acceptance_san,
            accepted_by_best_defense=audit.defense_accepted,
            material_conceded=audit.material_conceded,
        ),
        best_defense_san=audit.best_defense_san,
        terminal_status=audit.terminal_status,
        exchange=exchange_out(audit.exchange),
        non_obviousness=non_obviousness_out(audit.non_obviousness),
        detector_version=audit.detector_version,
        engine_identity=engine_identity_out(audit.engine_identity),
        budgets=node_budgets_out(audit),
    )
