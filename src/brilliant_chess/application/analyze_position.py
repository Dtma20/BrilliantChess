"""Caso de uso ``AnalyzePosition``: descoberta + confirmacao individual.

Discovery encontra candidatas com MultiPV amplo. Confirmacao reanalisa cada
candidata isoladamente com ``root_moves``, e e o resultado da confirmacao que
define o rank e a perda de pontos esperados. O rank bruto do MultiPV nunca e
usado como veredito.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.expected_points import expected_points_loss
from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    Position,
)
from brilliant_chess.domain.values import Color, WarningCode
from brilliant_chess.ports.board import BoardService
from brilliant_chess.ports.engine import ChessEngine

_MISSING_ENGINE_IDENTITY = EngineIdentity(
    name="unknown",
    version="unknown",
    binary_sha256="",
    nnue_name=None,
)


@dataclass(frozen=True)
class AnalysisRequest:
    position: Position
    discovery_budget: AnalysisBudget
    confirmation_budget: AnalysisBudget
    multipv: int = 8
    max_candidates: int = 5
    allow_missing_identity: bool = False


@dataclass(frozen=True)
class Candidate:
    move_uci: str
    move_san: str
    rank: int
    expected_points_after: float
    expected_points_loss: float
    centipawns: int | None
    mate_in: int | None
    depth: int
    nodes: int
    pv_uci: tuple[str, ...]
    pv_san: tuple[str, ...]
    discovery_rank: int | None = None

    @property
    def is_best(self) -> bool:
        return self.rank == 1


@dataclass(frozen=True)
class PositionAnalysis:
    position: Position
    side_to_move: Color
    engine: EngineIdentity
    expected_points_before: float
    candidates: tuple[Candidate, ...]
    warnings: tuple[WarningCode, ...]

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None


def analyze_position(
    engine: ChessEngine,
    board: BoardService,
    request: AnalysisRequest,
) -> PositionAnalysis:
    """Analisa a posicao e devolve candidatas confirmadas, ordenadas."""
    discovery = engine.analyze(request.position, request.discovery_budget, multipv=request.multipv)
    if not discovery:
        return PositionAnalysis(
            position=request.position,
            side_to_move=request.position.side_to_move,
            engine=_identity(engine, request.allow_missing_identity),
            expected_points_before=0.0,
            candidates=(),
            warnings=(WarningCode.SHALLOW_BUDGET,),
        )

    shortlist = tuple(discovery[: request.max_candidates])
    discovery_order = {item.move_uci: index + 1 for index, item in enumerate(shortlist)}
    confirmed = _confirm(engine, request, shortlist)
    confirmed.sort(key=lambda item: (-item.expected_points, item.move_uci))

    best_points = confirmed[0].expected_points
    context = _CandidateContext(best_points=best_points, board=board, position=request.position)
    candidates = tuple(
        _to_candidate(
            evaluation=evaluation,
            rank=index + 1,
            discovery_rank=discovery_order.get(evaluation.move_uci),
            context=context,
        )
        for index, evaluation in enumerate(confirmed)
    )
    return PositionAnalysis(
        position=request.position,
        side_to_move=request.position.side_to_move,
        engine=_identity(engine, request.allow_missing_identity),
        expected_points_before=best_points,
        candidates=candidates,
        warnings=_warnings(shortlist, confirmed),
    )


def _confirm(
    engine: ChessEngine,
    request: AnalysisRequest,
    shortlist: Sequence[MoveEvaluation],
) -> list[MoveEvaluation]:
    confirmed: list[MoveEvaluation] = []
    for item in shortlist:
        result = engine.analyze(
            request.position,
            request.confirmation_budget,
            multipv=1,
            root_moves=[Move(item.move_uci)],
        )
        confirmed.append(result[0] if result else item)
    return confirmed


def _identity(engine: ChessEngine, allow_missing: bool) -> EngineIdentity:
    try:
        return engine.identity()
    except (AttributeError, EngineError):
        if not allow_missing:
            raise
        return _MISSING_ENGINE_IDENTITY


@dataclass(frozen=True)
class _CandidateContext:
    """Agrupa o que a conversao precisa alem da propria avaliacao."""

    best_points: float
    board: BoardService
    position: Position


def _to_candidate(
    evaluation: MoveEvaluation,
    rank: int,
    discovery_rank: int | None,
    context: _CandidateContext,
) -> Candidate:
    best_points = context.best_points
    board = context.board
    position = context.position
    loss = expected_points_loss(best_points, evaluation.expected_points)
    pv_san = evaluation.pv.moves_san or board.pv_san(position, evaluation.pv.moves_uci)
    return Candidate(
        move_uci=evaluation.move_uci,
        move_san=evaluation.move_san,
        rank=rank,
        expected_points_after=evaluation.expected_points,
        expected_points_loss=loss.value,
        centipawns=evaluation.evaluation.centipawns,
        mate_in=evaluation.evaluation.mate_in,
        depth=evaluation.depth,
        nodes=evaluation.nodes,
        pv_uci=evaluation.pv.moves_uci,
        pv_san=tuple(pv_san),
        discovery_rank=discovery_rank,
    )


def _warnings(
    shortlist: Sequence[MoveEvaluation],
    confirmed: Sequence[MoveEvaluation],
) -> tuple[WarningCode, ...]:
    warnings: list[WarningCode] = []
    if shortlist and confirmed and shortlist[0].move_uci != confirmed[0].move_uci:
        warnings.append(WarningCode.RANK_CHANGED_AFTER_CONFIRMATION)
    if any(item.evaluation.is_mate for item in confirmed):
        warnings.append(WarningCode.MATE_SCORE_PRESENT)
    if any(item.evaluation.wdl is None for item in confirmed):
        warnings.append(WarningCode.WDL_UNAVAILABLE_FALLBACK_USED)
    return tuple(warnings)
