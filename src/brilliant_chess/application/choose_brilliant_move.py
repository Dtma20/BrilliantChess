"""Selecao auditavel de jogadas brilhantes sob as regras ``strict_v1``."""

from __future__ import annotations

from dataclasses import dataclass, replace

from brilliant_chess.application.analyze_position import (
    AnalysisRequest,
    Candidate,
    analyze_position,
)
from brilliant_chess.application.sacrifice_detector import detect_destination_offer
from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.expected_points import expected_points_loss
from brilliant_chess.domain.gates import GateInputs, GateResult, evaluate_gates
from brilliant_chess.domain.material import material_delta
from brilliant_chess.domain.models import AnalysisBudget, Move, MoveEvaluation, Position
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.sacrifice import (
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.scoring import BrilliantDecision, ScoringInputs, decide
from brilliant_chess.domain.values import GateId, GateStatus
from brilliant_chess.ports.board import BoardService
from brilliant_chess.ports.engine import ChessEngine

_OPPONENT_REPLY_INDEX = 1
_PV_WITH_REPLY_LENGTH = 2


@dataclass(frozen=True)
class StrictSearchBudget:
    discovery: AnalysisBudget
    confirmation: AnalysisBudget
    best_defense: AnalysisBudget
    stability: AnalysisBudget | None
    multipv: int
    max_candidates: int


@dataclass(frozen=True)
class CandidateAudit:
    candidate: Candidate
    decision: BrilliantDecision
    best_defense_uci: str | None
    stability_depth: int | None


@dataclass(frozen=True)
class BrilliantMoveChoice:
    move: Move | None
    selected: CandidateAudit | None
    candidates: tuple[CandidateAudit, ...]


@dataclass(frozen=True)
class _AuditContext:
    engine: ChessEngine
    board: BoardService
    position: Position
    rules: RuleSet
    budget: StrictSearchBudget
    candidates: tuple[Candidate, ...]
    expected_points_before: float


@dataclass(frozen=True)
class _MeasuredEvidence:
    candidate: Candidate
    best_defense_uci: str | None
    material_conceded: float
    stable: MoveEvaluation | None


def choose_brilliant_move(
    engine: ChessEngine,
    board: BoardService,
    position: Position,
    rules: RuleSet,
    budget: StrictSearchBudget,
) -> BrilliantMoveChoice:
    """Confirma candidatas, mede defesas e seleciona somente as elegiveis."""
    analysis = analyze_position(
        engine,
        board,
        AnalysisRequest(
            position=position,
            discovery_budget=budget.discovery,
            confirmation_budget=budget.confirmation,
            multipv=budget.multipv,
            max_candidates=budget.max_candidates,
        ),
    )
    context = _AuditContext(
        engine, board, position, rules, budget, analysis.candidates, analysis.expected_points_before
    )
    audits = tuple(_audit_candidate(context, candidate) for candidate in analysis.candidates)
    eligible = sorted(
        (audit for audit in audits if audit.decision.selectable),
        key=lambda audit: (
            -audit.decision.score,
            audit.candidate.expected_points_loss,
            audit.candidate.move_uci,
        ),
    )
    selected = eligible[0] if eligible else None
    move = None
    if selected is not None:
        move = Move(selected.candidate.move_uci, selected.candidate.move_san)
    rejected = tuple(audit for audit in audits if not audit.decision.selectable)
    return BrilliantMoveChoice(move=move, selected=selected, candidates=tuple(eligible) + rejected)


def _audit_candidate(context: _AuditContext, candidate: Candidate) -> CandidateAudit:
    engine = context.engine
    board = context.board
    position = context.position
    rules = context.rules
    budget = context.budget
    move = board.normalize_move(position, candidate.move_uci)
    after = board.view(position.fen, (move.uci,))
    sacrifice = detect_destination_offer(
        board,
        position,
        move.uci,
        material_values=rules.material_values,
        confidence_weights=rules.sacrifice.confidence_weights,
    )
    defense = _first(engine, after.position, budget.best_defense)
    best_defense_uci = None if defense is None else defense.move_uci
    defense_loss = None
    depends_on_opponent_error = False
    material_conceded = 0.0
    if defense is not None:
        defender_points_from_mover_pov = defense.evaluation.flipped().expected_points
        defense_loss = expected_points_loss(
            candidate.expected_points_after, defender_points_from_mover_pov
        ).value
        depends_on_opponent_error = (
            len(candidate.pv_uci) < _PV_WITH_REPLY_LENGTH
            or defense.move_uci != candidate.pv_uci[_OPPONENT_REPLY_INDEX]
        )
        if defense.move_uci in sacrifice.acceptance_moves:
            accepted = board.view(after.position.fen, (defense.move_uci,))
            material_conceded = max(
                0.0,
                -material_delta(
                    after.snapshot.placement,
                    accepted.snapshot.placement,
                    position.side_to_move,
                    rules.material_values,
                ),
            )

    stable = (
        None
        if budget.stability is None
        else _first(engine, position, budget.stability, root_move=move)
    )
    drift = None if stable is None else stable.expected_points - candidate.expected_points_after
    overlap = None if stable is None else candidate_pv_overlap(candidate, stable)
    sacrifice = _with_measured_signals(
        sacrifice,
        _MeasuredEvidence(candidate, best_defense_uci, material_conceded, stable),
        rules,
    )
    inputs = GateInputs(
        is_legal=True,
        expected_points_before=context.expected_points_before,
        expected_points_after=candidate.expected_points_after,
        expected_points_loss=candidate.expected_points_loss,
        confirmed_rank=candidate.rank,
        sacrifice=sacrifice,
        expected_points_loss_after_best_defense=defense_loss,
        depends_on_opponent_error=depends_on_opponent_error,
        expected_points_drift=drift,
        pv_overlap_plies=overlap,
        sacrifice_persisted=sacrifice.signals.persists_under_deeper_search,
    )
    equivalent = (
        sum(
            other.expected_points_loss <= rules.selection.uniqueness_equivalence_margin
            for other in context.candidates
        )
        - 1
    )
    scoring = ScoringInputs(
        expected_points_loss=candidate.expected_points_loss,
        sacrifice=sacrifice,
        net_material_conceded=material_conceded,
        replies_preserving_evaluation=int(
            defense_loss is not None and defense_loss <= rules.quality.max_expected_points_loss
        ),
        total_legal_replies=max(1, len(after.legal_moves)),
        forcing_moves_in_pv=int(best_defense_uci in sacrifice.acceptance_moves),
        pv_length=len(candidate.pv_uci),
        equivalent_alternatives=equivalent,
        expected_points_drift=drift,
        pv_overlap_plies=overlap,
        sacrifice_persisted=sacrifice.signals.persists_under_deeper_search,
    )
    gates = _strict_gates(inputs, rules, has_stability_evidence=stable is not None)
    return CandidateAudit(
        candidate=candidate,
        decision=decide(gates, scoring, rules),
        best_defense_uci=best_defense_uci,
        stability_depth=None if stable is None else stable.depth,
    )


def _strict_gates(
    inputs: GateInputs,
    rules: RuleSet,
    *,
    has_stability_evidence: bool,
) -> tuple[GateResult, ...]:
    gates = evaluate_gates(inputs, rules)
    if has_stability_evidence:
        return gates
    return tuple(
        replace(
            gate,
            status=GateStatus.INDETERMINATE,
            measured_value=None,
            explanation="Evidencia de estabilidade obrigatoria ausente",
        )
        if gate.gate_id is GateId.STABILITY
        else gate
        for gate in gates
    )


def _first(
    engine: ChessEngine,
    position: Position,
    budget: AnalysisBudget,
    *,
    root_move: Move | None = None,
) -> MoveEvaluation | None:
    try:
        result = engine.analyze(
            position, budget, multipv=1, root_moves=None if root_move is None else (root_move,)
        )
    except EngineError:
        return None
    return result[0] if result else None


def candidate_pv_overlap(candidate: Candidate, stable: MoveEvaluation) -> int:
    overlap = 0
    for left, right in zip(candidate.pv_uci, stable.pv.moves_uci, strict=False):
        if left != right:
            break
        overlap += 1
    return overlap


def _with_measured_signals(
    sacrifice: SacrificeEvidence,
    measured: _MeasuredEvidence,
    rules: RuleSet,
) -> SacrificeEvidence:
    if not sacrifice.detected:
        return sacrifice
    accepted_in_candidate_pv = any(
        move in sacrifice.acceptance_moves for move in measured.candidate.pv_uci[1:]
    )
    accepted_in_stable_pv = (
        None
        if measured.stable is None
        else any(move in sacrifice.acceptance_moves for move in measured.stable.pv.moves_uci[1:])
    )
    signals = SacrificeSignals(
        legal_capture_available=True,
        material_deficit_in_acceptance=measured.material_conceded > 0.0,
        engine_considers_acceptance=measured.best_defense_uci in sacrifice.acceptance_moves,
        tactical_mechanism_in_pv=accepted_in_candidate_pv,
        persists_under_deeper_search=accepted_in_stable_pv,
    )
    return replace(
        sacrifice,
        material_trajectory=(0.0, -measured.material_conceded)
        if measured.material_conceded
        else (),
        confidence=sacrifice_confidence(signals, rules.sacrifice.confidence_weights),
        reasons=reasons_for(signals),
        signals=signals,
    )
