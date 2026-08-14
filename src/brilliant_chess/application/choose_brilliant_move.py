"""Selecao auditavel de jogadas brilhantes sob regras strict versionadas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from brilliant_chess.application.analyze_position import (
    AnalysisRequest,
    Candidate,
    analyze_position,
)
from brilliant_chess.application.exchange_sacrifice import detect_exchange_aware_sacrifice
from brilliant_chess.application.sacrifice_detector import detect_sacrifice
from brilliant_chess.domain.errors import EngineError, InvalidEvaluationError
from brilliant_chess.domain.exchange import ExchangeEvidence
from brilliant_chess.domain.expected_points import expected_points_loss
from brilliant_chess.domain.gates import GateInputs, GateResult, evaluate_gates
from brilliant_chess.domain.material import material_delta
from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    Position,
)
from brilliant_chess.domain.non_obviousness import (
    NonObviousnessCondition,
    NonObviousnessEvidence,
)
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.sacrifice import (
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.scoring import BrilliantDecision, ScoringInputs, decide
from brilliant_chess.domain.values import (
    GAME_STATUS_TEXTS,
    GameStatus,
    GateId,
    GateStatus,
)
from brilliant_chess.ports.board import BoardService
from brilliant_chess.ports.engine import ChessEngine

_OPPONENT_REPLY_INDEX = 1
_PV_WITH_REPLY_LENGTH = 2
_NEAR_BRILLIANT_SAFETY_GATES = frozenset(
    {
        GateId.LEGAL,
        GateId.SOUNDNESS,
        GateId.NOT_BAD_AFTER,
        GateId.STABILITY,
    }
)

#: Empate vale meio ponto. Isto e regra do jogo, nao estimativa de motor.
DRAW_EXPECTED_POINTS: Final[float] = 0.5
EXCHANGE_DETECTOR_VERSION: Final[str] = "exchange_aware_v1"


@dataclass(frozen=True)
class PositionHistory:
    """Caminho ate a posicao raiz.

    Repeticao e a regra dos cinquenta lances nao estao na FEN. Sem o caminho, o
    ``BoardService`` nao consegue declarar tripla repeticao e o motor tambem nao
    a ve, porque recebe apenas a posicao.
    """

    initial_fen: str
    moves_uci: tuple[str, ...] = ()

    @classmethod
    def from_position(cls, position: Position) -> PositionHistory:
        return cls(initial_fen=position.fen, moves_uci=())


@dataclass(frozen=True)
class StrictSearchBudget:
    discovery: AnalysisBudget
    confirmation: AnalysisBudget
    best_defense: AnalysisBudget
    stability: AnalysisBudget | None
    multipv: int
    max_candidates: int
    shallow: AnalysisBudget | None = None
    shallow_multipv: int = 5


@dataclass(frozen=True)
class CandidateAudit:
    candidate: Candidate
    decision: BrilliantDecision
    best_defense_uci: str | None
    stability_depth: int | None
    #: SAN da melhor defesa medida, para a auditoria falar em notacao de xadrez.
    best_defense_san: str | None = None
    #: SAN das capturas que aceitam a peca oferecida.
    acceptance_san: tuple[str, ...] = ()
    #: A melhor defesa medida aceita a oferta.
    defense_accepted: bool = False
    #: Material liquido concedido quando a melhor defesa aceita.
    material_conceded: float = 0.0
    #: Desfecho imediato da candidata, quando ela encerra a partida.
    terminal_status: GameStatus | None = None
    #: Evidencia de troca, disponivel apenas na auditoria ``strict_v2``.
    exchange: ExchangeEvidence | None = None
    #: Evidencia de surpresa rasa/profunda, disponivel apenas em ``strict_v2``.
    non_obviousness: NonObviousnessEvidence | None = None
    #: Versao do detector usado para a evidencia de troca.
    detector_version: str | None = None
    #: Identidade do motor que produziu a auditoria.
    engine_identity: EngineIdentity | None = None
    #: Orcamentos usados em cada estagio da auditoria.
    discovery_budget: AnalysisBudget | None = None
    confirmation_budget: AnalysisBudget | None = None
    best_defense_budget: AnalysisBudget | None = None
    stability_budget: AnalysisBudget | None = None
    shallow_budget: AnalysisBudget | None = None
    shallow_multipv: int | None = None


@dataclass(frozen=True)
class BrilliantMoveChoice:
    move: Move | None
    selected: CandidateAudit | None
    candidates: tuple[CandidateAudit, ...]
    near_selected: CandidateAudit | None = None


@dataclass(frozen=True)
class _AuditContext:
    engine: ChessEngine
    board: BoardService
    position: Position
    rules: RuleSet
    budget: StrictSearchBudget
    candidates: tuple[Candidate, ...]
    expected_points_before: float
    history: PositionHistory
    shallow: dict[str, tuple[MoveEvaluation, int]] | None = None


@dataclass(frozen=True)
class _MeasuredEvidence:
    candidate: Candidate
    best_defense_uci: str | None
    material_conceded: float
    stable: MoveEvaluation | None


def choose_brilliant_move(
    engine: ChessEngine,
    board: BoardService,
    history: PositionHistory,
    rules: RuleSet,
    budget: StrictSearchBudget,
) -> BrilliantMoveChoice:
    """Confirma candidatas, mede defesas e seleciona somente as elegiveis.

    A posicao raiz sai do proprio ``history``: assim caminho e posicao nao podem
    divergir, e as regras que dependem de historico ficam sempre disponiveis.
    """
    position = board.position_after(history.initial_fen, history.moves_uci)
    path = history
    shallow = _shallow_evidence(engine, position, budget) if rules.id == "strict_v2" else None
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
        engine,
        board,
        position,
        rules,
        budget,
        analysis.candidates,
        analysis.expected_points_before,
        path,
        shallow,
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
    near_selected = None if selected is not None else _select_near_brilliant(audits, rules)
    move = None
    if selected is not None:
        move = Move(selected.candidate.move_uci, selected.candidate.move_san)
    rejected = tuple(audit for audit in audits if not audit.decision.selectable)
    return BrilliantMoveChoice(
        move=move,
        selected=selected,
        candidates=tuple(eligible) + rejected,
        near_selected=near_selected,
    )


def _shallow_evidence(
    engine: ChessEngine,
    position: Position,
    budget: StrictSearchBudget,
) -> dict[str, tuple[MoveEvaluation, int]] | None:
    if budget.shallow is None:
        return None
    try:
        result = engine.analyze(position, budget.shallow, multipv=budget.shallow_multipv)
    except EngineError:
        return {}
    return {
        item.move_uci: (item, item.multipv_rank or index)
        for index, item in enumerate(result, start=1)
    }


def _select_near_brilliant(
    audits: tuple[CandidateAudit, ...], rules: RuleSet
) -> CandidateAudit | None:
    """Escolhe uma candidata auditada que falhou apenas em criterios nao-seguranca."""
    safe = (
        audit
        for audit in audits
        if audit.candidate.expected_points_loss <= rules.selection.safe_max_expected_points_loss
        and _near_brilliant_safety_gates_passed(audit)
    )
    return min(
        safe,
        key=lambda audit: (
            audit.candidate.expected_points_loss,
            _winning_mate_distance(audit),
            -audit.decision.score,
            audit.candidate.move_uci,
        ),
        default=None,
    )


def _winning_mate_distance(audit: CandidateAudit) -> float:
    mate_in = audit.candidate.mate_in
    return float(mate_in) if mate_in is not None and mate_in > 0 else float("inf")


def _near_brilliant_safety_gates_passed(audit: CandidateAudit) -> bool:
    statuses = {gate.gate_id: gate.passed for gate in audit.decision.gates}
    return all(statuses.get(gate_id, False) for gate_id in _NEAR_BRILLIANT_SAFETY_GATES)


def _audit_candidate(context: _AuditContext, candidate: Candidate) -> CandidateAudit:
    if context.rules.id == "strict_v2":
        return _audit_candidate_v2(context, candidate)
    return _audit_candidate_v1(context, candidate)


def _audit_candidate_v1(context: _AuditContext, candidate: Candidate) -> CandidateAudit:
    engine = context.engine
    board = context.board
    position = context.position
    rules = context.rules
    budget = context.budget
    move = board.normalize_move(position, candidate.move_uci)
    after = board.view(context.history.initial_fen, (*context.history.moves_uci, move.uci))
    terminal_status = after.status if after.status.is_finished else None
    terminal_checkmate = after.status is GameStatus.CHECKMATE
    terminal_draw = terminal_status is not None and not terminal_checkmate
    if terminal_draw:
        candidate = _as_immediate_draw(candidate, context.expected_points_before)
    sacrifice = detect_sacrifice(
        board,
        position,
        move.uci,
        material_values=rules.material_values,
        confidence_weights=rules.sacrifice.confidence_weights,
    )
    defense = (
        None if terminal_status is not None else _first(engine, after.position, budget.best_defense)
    )
    best_defense_uci = None if defense is None else defense.move_uci
    defense_loss = 0.0 if terminal_status is not None else None
    best_defense_disagrees = False
    depends_on_opponent_error = False
    material_conceded = 0.0
    if defense is not None:
        defender_points_from_mover_pov = defense.evaluation.flipped().expected_points
        try:
            defense_loss = expected_points_loss(
                candidate.expected_points_after,
                defender_points_from_mover_pov,
                tolerance=rules.robustness.max_ep_drift_on_deeper_search,
            ).value
        except InvalidEvaluationError:
            best_defense_disagrees = True
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
        if terminal_status is not None or budget.stability is None
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
    gates = _strict_gates(
        inputs,
        rules,
        has_stability_evidence=stable is not None,
        best_defense_disagrees=best_defense_disagrees,
        terminal_status=terminal_status,
    )
    return CandidateAudit(
        candidate=candidate,
        decision=decide(gates, scoring, rules),
        best_defense_uci=best_defense_uci,
        stability_depth=None if stable is None else stable.depth,
        best_defense_san=_san_of(board, after.position, best_defense_uci),
        acceptance_san=_each_san(board, after.position, sacrifice.acceptance_moves),
        defense_accepted=best_defense_uci is not None
        and best_defense_uci in sacrifice.acceptance_moves,
        material_conceded=material_conceded,
        terminal_status=terminal_status,
    )


def _audit_candidate_v2(context: _AuditContext, candidate: Candidate) -> CandidateAudit:
    engine = context.engine
    board = context.board
    position = context.position
    rules = context.rules
    budget = context.budget
    move = board.normalize_move(position, candidate.move_uci)
    after = board.view(context.history.initial_fen, (*context.history.moves_uci, move.uci))
    terminal_status = after.status if after.status.is_finished else None
    terminal_checkmate = terminal_status is GameStatus.CHECKMATE
    terminal_draw = terminal_status is not None and not terminal_checkmate
    if terminal_draw:
        candidate = _as_immediate_draw(candidate, context.expected_points_before)
    sacrifice = detect_exchange_aware_sacrifice(
        board,
        context.history.initial_fen,
        context.history.moves_uci,
        move.uci,
        material_values=rules.material_values,
        thresholds=rules.sacrifice,
    )
    defense = (
        None if terminal_status is not None else _first(engine, after.position, budget.best_defense)
    )
    best_defense_uci = None if defense is None else defense.move_uci
    defense_loss = 0.0 if terminal_status is not None else None
    best_defense_disagrees = False
    depends_on_opponent_error = False
    material_conceded = 0.0
    if defense is not None:
        defender_points_from_mover_pov = defense.evaluation.flipped().expected_points
        try:
            defense_loss = expected_points_loss(
                candidate.expected_points_after,
                defender_points_from_mover_pov,
                tolerance=rules.robustness.max_ep_drift_on_deeper_search,
            ).value
        except InvalidEvaluationError:
            best_defense_disagrees = True
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
        if terminal_status is not None or budget.stability is None
        else _first(engine, position, budget.stability, root_move=move)
    )
    drift = None if stable is None else stable.expected_points - candidate.expected_points_after
    overlap = None if stable is None else candidate_pv_overlap(candidate, stable)
    sacrifice = _with_measured_signals(
        sacrifice,
        _MeasuredEvidence(candidate, best_defense_uci, material_conceded, stable),
        rules,
    )
    non_obviousness = _non_obviousness_evidence(context, candidate, move)
    engine_identity = _safe_engine_identity(engine)
    if engine_identity is None:
        non_obviousness = replace(non_obviousness, condition=None)
    inputs = GateInputs(
        is_legal=True,
        expected_points_before=context.expected_points_before,
        expected_points_after=candidate.expected_points_after,
        expected_points_loss=candidate.expected_points_loss,
        confirmed_rank=candidate.rank,
        sacrifice=sacrifice,
        non_obviousness=non_obviousness,
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
    gates = _strict_gates(
        inputs,
        rules,
        has_stability_evidence=stable is not None,
        best_defense_disagrees=best_defense_disagrees,
        terminal_status=terminal_status,
    )
    return CandidateAudit(
        candidate=candidate,
        decision=decide(gates, scoring, rules),
        best_defense_uci=best_defense_uci,
        stability_depth=None if stable is None else stable.depth,
        best_defense_san=_san_of(board, after.position, best_defense_uci),
        acceptance_san=_each_san(board, after.position, sacrifice.acceptance_moves),
        defense_accepted=best_defense_uci is not None
        and best_defense_uci in sacrifice.acceptance_moves,
        material_conceded=material_conceded,
        terminal_status=terminal_status,
        exchange=sacrifice.exchange,
        non_obviousness=non_obviousness,
        detector_version=EXCHANGE_DETECTOR_VERSION,
        engine_identity=engine_identity,
        discovery_budget=budget.discovery,
        confirmation_budget=budget.confirmation,
        best_defense_budget=budget.best_defense,
        stability_budget=budget.stability,
        shallow_budget=budget.shallow,
        shallow_multipv=budget.shallow_multipv if budget.shallow is not None else None,
    )


def _non_obviousness_evidence(
    context: _AuditContext,
    candidate: Candidate,
    move: Move,
) -> NonObviousnessEvidence:
    budget = context.budget
    if budget.shallow is None:
        return NonObviousnessEvidence()
    shallow_result = None
    shallow_rank = None
    if context.shallow is not None:
        shallow_entry = context.shallow.get(candidate.move_uci)
        if shallow_entry is not None:
            shallow_result, shallow_rank = shallow_entry
    if shallow_result is None:
        shallow_result = _first(context.engine, context.position, budget.shallow, root_move=move)
    if shallow_result is None:
        return NonObviousnessEvidence(
            shallow_nodes=budget.shallow.nodes,
            shallow_multipv=budget.shallow_multipv,
            deep_rank=candidate.rank,
            deep_expected_points=candidate.expected_points_after,
        )
    improvement = candidate.expected_points_after - shallow_result.expected_points
    condition = _non_obviousness_condition(
        shallow_rank,
        candidate.rank,
        improvement,
        context.rules,
    )
    return NonObviousnessEvidence(
        shallow_rank=shallow_rank,
        deep_rank=candidate.rank,
        shallow_expected_points=shallow_result.expected_points,
        deep_expected_points=candidate.expected_points_after,
        expected_points_improvement=improvement,
        shallow_nodes=budget.shallow.nodes,
        shallow_multipv=budget.shallow_multipv,
        condition=condition,
    )


def _non_obviousness_condition(
    shallow_rank: int | None,
    deep_rank: int,
    improvement: float,
    rules: RuleSet,
) -> NonObviousnessCondition | None:
    thresholds = rules.non_obviousness
    ep_passes = improvement >= thresholds.min_expected_points_improvement
    rank_improvement = (
        shallow_rank is not None and shallow_rank - deep_rank >= thresholds.min_rank_improvement
    )
    shallow_escape = (
        shallow_rank is not None
        and shallow_rank > thresholds.max_obvious_shallow_rank
        and deep_rank <= thresholds.max_confirmed_rank
    )
    if ep_passes and rank_improvement:
        return NonObviousnessCondition.EP_AND_RANK_IMPROVEMENT
    if ep_passes:
        return NonObviousnessCondition.EP_IMPROVEMENT
    if rank_improvement:
        return NonObviousnessCondition.RANK_IMPROVEMENT
    if shallow_escape:
        return NonObviousnessCondition.SHALLOW_OBVIOUSNESS
    return None


def _safe_engine_identity(engine: ChessEngine) -> EngineIdentity | None:
    try:
        return engine.identity()
    except (AttributeError, EngineError):
        return None


def _as_immediate_draw(candidate: Candidate, expected_points_before: float) -> Candidate:
    """Reescreve a avaliacao de uma candidata que encerra a partida em empate.

    O motor recebe apenas a posicao, entao nao ve repeticao nem a regra dos
    cinquenta lances e pode devolver uma vantagem grande para uma linha que, na
    partida real, termina em meio ponto. Quem manda aqui e o tabuleiro.
    """
    return replace(
        candidate,
        expected_points_after=DRAW_EXPECTED_POINTS,
        expected_points_loss=max(0.0, expected_points_before - DRAW_EXPECTED_POINTS),
        centipawns=0,
        mate_in=None,
    )


def _each_san(
    board: BoardService, position: Position, moves_uci: tuple[str, ...]
) -> tuple[str, ...]:
    """SAN de cada lance alternativo, cada um a partir da mesma posicao."""
    return tuple(_san(board, position, uci) for uci in moves_uci)


def _san_of(board: BoardService, position: Position, move_uci: str | None) -> str | None:
    return None if move_uci is None else _san(board, position, move_uci)


def _san(board: BoardService, position: Position, move_uci: str) -> str:
    normalized = board.normalize_move(position, move_uci)
    return normalized.san or normalized.uci


def _strict_gates(
    inputs: GateInputs,
    rules: RuleSet,
    *,
    has_stability_evidence: bool,
    best_defense_disagrees: bool,
    terminal_status: GameStatus | None,
) -> tuple[GateResult, ...]:
    gates = evaluate_gates(inputs, rules)
    if terminal_status is GameStatus.CHECKMATE:
        gates = _mark_gate_passed(
            gates,
            GateId.SOUNDNESS,
            "Mate confirmado pelo tabuleiro; nao ha defesa legal",
        )
        gates = _mark_gate_passed(
            gates,
            GateId.STABILITY,
            "Mate confirmado pelo tabuleiro; nao ha linha adicional a estabilizar",
        )
    elif terminal_status is not None:
        # Empate terminal nao tem defesa nem continuacao. O custo de escolher
        # um empate aparece em GATE_QUALITY_001, com EP fixado em 0.5.
        outcome = GAME_STATUS_TEXTS[terminal_status]
        gates = _mark_gate_passed(
            gates,
            GateId.SOUNDNESS,
            f"{outcome} confirmado pelo tabuleiro; a partida termina aqui",
        )
        gates = _mark_gate_passed(
            gates,
            GateId.STABILITY,
            f"{outcome} confirmado pelo tabuleiro; nao ha linha posterior a estabilizar",
        )
    elif not has_stability_evidence:
        gates = _mark_gate_indeterminate(
            gates,
            GateId.STABILITY,
            "Evidencia de estabilidade obrigatoria ausente",
        )
    if best_defense_disagrees:
        gates = _mark_gate_indeterminate(
            gates,
            GateId.SOUNDNESS,
            (
                "Discordancia entre confirmacao e melhor defesa excede "
                f"{rules.robustness.max_ep_drift_on_deeper_search:.4f} EP"
            ),
        )
    return gates


def _mark_gate_passed(
    gates: tuple[GateResult, ...], gate_id: GateId, explanation: str
) -> tuple[GateResult, ...]:
    return tuple(
        replace(
            gate,
            status=GateStatus.PASSED,
            measured_value=0.0,
            explanation=explanation,
        )
        if gate.gate_id is gate_id
        else gate
        for gate in gates
    )


def _mark_gate_indeterminate(
    gates: tuple[GateResult, ...],
    gate_id: GateId,
    explanation: str,
) -> tuple[GateResult, ...]:
    return tuple(
        replace(
            gate,
            status=GateStatus.INDETERMINATE,
            measured_value=None,
            explanation=explanation,
        )
        if gate.gate_id is gate_id
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
