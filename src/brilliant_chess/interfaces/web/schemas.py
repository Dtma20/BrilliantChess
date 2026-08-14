"""Contratos JSON da interface web. Versionados junto com a CLI."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from brilliant_chess.application import play_match
from brilliant_chess.application.analyze_position import Candidate, PositionAnalysis
from brilliant_chess.domain.exchange import ExchangeEvidence
from brilliant_chess.domain.gates import GateResult
from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity
from brilliant_chess.domain.non_obviousness import NonObviousnessEvidence
from brilliant_chess.domain.sacrifice import SacrificeEvidence
from brilliant_chess.domain.values import Color, GameStatus, PieceType, SacrificeKind
from brilliant_chess.ports.board import BoardView

#: Versao 2 acrescenta a evidencia de sacrificio e o desfecho terminal a
#: auditoria de cada lance do laboratorio.
API_SCHEMA_VERSION = "2"


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


class MatchProfileIn(_Model):
    strength_key: str = "clube"
    policy: play_match.MatchPolicy = play_match.MatchPolicy.NORMAL


class NewMatchIn(_Model):
    white: MatchProfileIn = MatchProfileIn(
        strength_key="maximo", policy=play_match.MatchPolicy.STRICT_V1
    )
    black: MatchProfileIn = MatchProfileIn(
        strength_key="iniciante", policy=play_match.MatchPolicy.NORMAL
    )
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


class MatchProfileOut(_Model):
    strength: StrengthOut
    policy: play_match.MatchPolicy


class GateOut(_Model):
    gate_id: str
    status: str
    measured: float | int | str | bool | None
    threshold: float | int | str | bool | None
    explanation: str


class SacrificeOut(_Model):
    """Peca oferecida e como o adversario poderia aceitar."""

    kind: SacrificeKind
    offered_square: str
    offered_piece: PieceType
    nominal_value: float
    confidence: float
    acceptance_san: list[str]
    accepted_by_best_defense: bool
    material_conceded: float


class ExchangeOut(_Model):
    disposition: str
    material_before: float
    material_immediately_after: float
    material_after_best_acceptance: float | None
    material_captured_by_candidate: float
    material_lost_by_mover: float
    material_captured_later_by_mover: float
    net_material_concession: float
    sequence_uci: list[str]
    sequence_san: list[str]
    clean_trade: bool
    obvious_recapture: bool
    temporary_offer: bool
    favorable_trade: bool
    xray_recapture: bool


class NonObviousnessOut(_Model):
    shallow_rank: int | None
    deep_rank: int | None
    shallow_expected_points: float | None
    deep_expected_points: float | None
    expected_points_improvement: float | None
    shallow_nodes: int | None
    shallow_multipv: int | None
    condition: str | None


class EngineIdentityOut(_Model):
    name: str
    version: str
    binary_sha256: str
    nnue_name: str | None


class NodeBudgetsOut(_Model):
    discovery_nodes: int | None
    confirmation_nodes: int | None
    best_defense_nodes: int | None
    stability_nodes: int | None
    shallow_nodes: int | None
    shallow_multipv: int | None


class CandidateAuditOut(_Model):
    selected_uci: str
    selected_san: str
    score: float
    rule_set_version: str
    gates: list[GateOut]
    reason_codes: list[str]
    sacrifice: SacrificeOut | None = None
    best_defense_san: str | None = None
    exchange: ExchangeOut | None = None
    non_obviousness: NonObviousnessOut | None = None
    detector_version: str | None = None
    engine_identity: EngineIdentityOut | None = None
    budgets: NodeBudgetsOut | None = None
    #: Desfecho imediato do lance, quando ele encerra a partida.
    terminal_status: GameStatus | None = None


class MatchMoveOut(_Model):
    color: Color
    uci: str
    san: str
    selection: play_match.SelectionKind
    fallback: bool
    audit: CandidateAuditOut | None


class LabOut(_Model):
    """Parametros do laboratorio que o autoplay do navegador precisa conhecer."""

    schema_version: str = API_SCHEMA_VERSION
    max_fullmoves: int
    max_plies: int
    autoplay_delay_ms: int
    strict_policy: play_match.MatchPolicy


class MatchOut(_Model):
    schema_version: str = API_SCHEMA_VERSION
    match_id: str
    initial_fen: str
    white: MatchProfileOut
    black: MatchProfileOut
    board: BoardOut
    moves_uci: list[str]
    moves_san: list[str]
    moves: list[MatchMoveOut]
    result_text: str
    can_step: bool


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


def gate_out(gate: GateResult) -> GateOut:
    return GateOut(
        gate_id=gate.gate_id.value,
        status=gate.status.value,
        measured=gate.measured_value,
        threshold=gate.threshold,
        explanation=gate.explanation,
    )


def sacrifice_out(
    evidence: SacrificeEvidence,
    *,
    acceptance_san: tuple[str, ...],
    accepted_by_best_defense: bool,
    material_conceded: float,
) -> SacrificeOut | None:
    """``None`` quando nenhuma peca foi oferecida: ausencia nao e evidencia."""
    if (
        not evidence.detected
        or evidence.kind is None
        or evidence.offered_piece_square is None
        or evidence.offered_piece_type is None
    ):
        return None
    return SacrificeOut(
        kind=evidence.kind,
        offered_square=evidence.offered_piece_square,
        offered_piece=evidence.offered_piece_type,
        nominal_value=evidence.nominal_value,
        confidence=evidence.confidence,
        acceptance_san=list(acceptance_san),
        accepted_by_best_defense=accepted_by_best_defense,
        material_conceded=material_conceded,
    )


def exchange_out(evidence: ExchangeEvidence | None) -> ExchangeOut | None:
    if evidence is None:
        return None
    return ExchangeOut(
        disposition=evidence.disposition.value,
        material_before=evidence.material_before,
        material_immediately_after=evidence.material_immediately_after,
        material_after_best_acceptance=evidence.material_after_best_acceptance,
        material_captured_by_candidate=evidence.material_captured_by_candidate,
        material_lost_by_mover=evidence.material_lost_by_mover,
        material_captured_later_by_mover=evidence.material_captured_later_by_mover,
        net_material_concession=evidence.net_material_concession,
        sequence_uci=list(evidence.sequence_uci),
        sequence_san=list(evidence.sequence_san),
        clean_trade=evidence.clean_trade,
        obvious_recapture=evidence.obvious_recapture,
        temporary_offer=evidence.temporary_offer,
        favorable_trade=evidence.favorable_trade,
        xray_recapture=evidence.xray_recapture,
    )


def non_obviousness_out(evidence: NonObviousnessEvidence | None) -> NonObviousnessOut | None:
    if evidence is None:
        return None
    return NonObviousnessOut(
        shallow_rank=evidence.shallow_rank,
        deep_rank=evidence.deep_rank,
        shallow_expected_points=evidence.shallow_expected_points,
        deep_expected_points=evidence.deep_expected_points,
        expected_points_improvement=evidence.expected_points_improvement,
        shallow_nodes=evidence.shallow_nodes,
        shallow_multipv=evidence.shallow_multipv,
        condition=None if evidence.condition is None else evidence.condition.value,
    )


def engine_identity_out(identity: EngineIdentity | None) -> EngineIdentityOut | None:
    if identity is None:
        return None
    return EngineIdentityOut(
        name=identity.name,
        version=identity.version,
        binary_sha256=identity.binary_sha256,
        nnue_name=identity.nnue_name,
    )


def node_budgets_out(audit: play_match.MatchAudit) -> NodeBudgetsOut | None:
    budgets = (
        audit.discovery_budget,
        audit.confirmation_budget,
        audit.best_defense_budget,
        audit.stability_budget,
        audit.shallow_budget,
    )
    if not any(budget is not None for budget in budgets):
        return None
    return NodeBudgetsOut(
        discovery_nodes=_budget_nodes(audit.discovery_budget),
        confirmation_nodes=_budget_nodes(audit.confirmation_budget),
        best_defense_nodes=_budget_nodes(audit.best_defense_budget),
        stability_nodes=_budget_nodes(audit.stability_budget),
        shallow_nodes=_budget_nodes(audit.shallow_budget),
        shallow_multipv=audit.shallow_multipv,
    )


def _budget_nodes(budget: AnalysisBudget | None) -> int | None:
    return None if budget is None else budget.nodes


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
