"""Contratos JSON da interface web. Versionados junto com a CLI."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brilliant_chess.application.analyze_position import Candidate, PositionAnalysis
from brilliant_chess.domain.values import Color, GameStatus
from brilliant_chess.ports.board import BoardView

API_SCHEMA_VERSION = "1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StrengthOut(_Model):
    key: str
    label: str
    elo: int | None


class NewGameIn(_Model):
    human_color: Color = Color.WHITE
    strength_key: str = "clube"
    initial_fen: str | None = None


class MoveIn(_Model):
    move: str = Field(min_length=2, max_length=10)


class BoardOut(_Model):
    fen: str
    side_to_move: Color
    status: GameStatus
    is_check: bool
    legal_moves: list[str]
    last_move_uci: str | None
    move_number: int
    moves_san: list[str] = Field(default_factory=list)


class GameOut(_Model):
    schema_version: str = API_SCHEMA_VERSION
    game_id: str
    human_color: Color
    strength: StrengthOut
    board: BoardOut
    moves_san: list[str]
    moves_uci: list[str]
    engine_thinking: bool
    result_text: str


class BoardIn(_Model):
    fen: str | None = None
    moves: list[str] = Field(default_factory=list)


class AnalyzeIn(_Model):
    fen: str
    multipv: int | None = Field(default=None, ge=1, le=16)
    discovery_nodes: int | None = Field(default=None, gt=0)
    confirmation_nodes: int | None = Field(default=None, gt=0)


class ArrowOut(_Model):
    from_square: str
    to_square: str
    rank: int
    color: str
    label: str


class CandidateOut(_Model):
    move_uci: str
    move_san: str
    rank: int
    expected_points_after: float
    expected_points_loss: float
    centipawns: int | None
    mate_in: int | None
    evaluation_text: str
    depth: int
    nodes: int
    pv_san: list[str]


class AnalysisOut(_Model):
    schema_version: str = API_SCHEMA_VERSION
    fen: str
    side_to_move: Color
    engine_name: str
    engine_version: str
    nnue_name: str | None
    expected_points_before: float
    candidates: list[CandidateOut]
    arrows: list[ArrowOut]
    warnings: list[str]
    board: BoardOut


def board_out(view: BoardView) -> BoardOut:
    return BoardOut(
        fen=view.position.fen,
        side_to_move=view.position.side_to_move,
        status=view.status,
        is_check=view.is_check,
        legal_moves=[move.uci for move in view.legal_moves],
        last_move_uci=view.last_move_uci,
        move_number=view.move_number,
        moves_san=list(view.moves_san),
    )


def candidate_out(candidate: Candidate) -> CandidateOut:
    return CandidateOut(
        move_uci=candidate.move_uci,
        move_san=candidate.move_san,
        rank=candidate.rank,
        expected_points_after=candidate.expected_points_after,
        expected_points_loss=candidate.expected_points_loss,
        centipawns=candidate.centipawns,
        mate_in=candidate.mate_in,
        evaluation_text=evaluation_text(candidate),
        depth=candidate.depth,
        nodes=candidate.nodes,
        pv_san=list(candidate.pv_san),
    )


def evaluation_text(candidate: Candidate) -> str:
    """Texto do ponto de vista do lado a jogar, como em qualquer tabuleiro."""
    if candidate.mate_in is not None:
        sign = "" if candidate.mate_in > 0 else "-"
        return f"{sign}M{abs(candidate.mate_in)}"
    if candidate.centipawns is None:
        return "?"
    pawns = candidate.centipawns / 100.0
    return f"{pawns:+.2f}"


def analysis_out(
    analysis: PositionAnalysis,
    view: BoardView,
    arrows: list[ArrowOut],
) -> AnalysisOut:
    return AnalysisOut(
        fen=analysis.position.fen,
        side_to_move=analysis.side_to_move,
        engine_name=analysis.engine.name,
        engine_version=analysis.engine.version,
        nnue_name=analysis.engine.nnue_name,
        expected_points_before=analysis.expected_points_before,
        candidates=[candidate_out(item) for item in analysis.candidates],
        arrows=arrows,
        warnings=[warning.value for warning in analysis.warnings],
        board=board_out(view),
    )
