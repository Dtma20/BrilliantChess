"""Avaliacao de sacrificio com consciencia de troca para ``strict_v2``.

Mantem o detector historico de ``strict_v1`` separado: aqui a decisao usa a
trajetoria material medida nas linhas legais de captura, sem importar
``python-chess`` nem duplicar os tipos do portao de tabuleiro.
"""

from __future__ import annotations

from dataclasses import dataclass

from brilliant_chess.application.sacrifice_detector import (
    detect_destination_offer,
    detect_left_hanging,
)
from brilliant_chess.domain.exchange import (
    ExchangeDisposition,
    ExchangeEvidence,
    ExchangePly,
    ExchangeTrace,
)
from brilliant_chess.domain.material import MaterialValues, Piece, material_balance
from brilliant_chess.domain.models import Move, PositionSnapshot
from brilliant_chess.domain.rule_set import SacrificeThresholds
from brilliant_chess.domain.sacrifice import (
    NO_SACRIFICE,
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.values import Color, PieceType, ReasonCode, SacrificeKind
from brilliant_chess.ports.board import BoardService

_EMPTY_REASONS: tuple[ReasonCode, ...] = ()


@dataclass(frozen=True)
class _EvaluatedLine:
    trace: ExchangeTrace
    acceptance_moves: tuple[ExchangePly, ...]
    material_before: float
    material_immediately_after: float
    material_after_best_acceptance: float
    material_captured_by_candidate: float
    material_lost_by_mover: float
    material_captured_later_by_mover: float
    net_material_concession: float
    sequence_uci: tuple[str, ...]
    sequence_san: tuple[str, ...]
    clean_trade: bool
    obvious_recapture: bool
    temporary_offer: bool
    favorable_trade: bool
    xray_recapture: bool


def detect_exchange_aware_sacrifice(  # noqa: PLR0913 - public contract mirrors the task brief
    board: BoardService,
    initial_fen: str,
    moves_uci: tuple[str, ...],
    candidate_move: str,
    *,
    material_values: MaterialValues,
    thresholds: SacrificeThresholds,
) -> SacrificeEvidence:
    """Classifica trocas reais, recapturas e ofertas rejeitadas em ``strict_v2``."""
    position = board.position_after(initial_fen, moves_uci)
    normalized = board.normalize_move(position, candidate_move)
    destination = detect_destination_offer(
        board,
        position,
        normalized.uci,
        material_values=material_values,
    )
    if destination.detected:
        traces = board.exchange_lines(
            initial_fen,
            moves_uci,
            normalized.uci,
            max_plies=thresholds.exchange_search_plies,
        )
        line = _best_line(traces, material_values, thresholds, position.side_to_move)
        if line is None:
            return NO_SACRIFICE
        return _destination_result(destination, line, thresholds)

    left_hanging = detect_left_hanging(
        board,
        position,
        normalized.uci,
        material_values=material_values,
    )
    if left_hanging.detected:
        root = board.view(initial_fen, moves_uci).snapshot
        after = board.view(initial_fen, (*moves_uci, normalized.uci))
        line = _best_left_hanging_line(
            board,
            root,
            after.snapshot,
            normalized,
            left_hanging.acceptance_moves,
            material_values,
            thresholds,
            position.side_to_move,
        )
        if line is None:
            return NO_SACRIFICE
        return _left_hanging_result(left_hanging, line, thresholds)

    return NO_SACRIFICE


def _best_line(
    traces: tuple[ExchangeTrace, ...],
    material_values: MaterialValues,
    thresholds: SacrificeThresholds,
    mover: Color,
) -> _EvaluatedLine | None:
    evaluated = tuple(
        _evaluate_trace(trace, trace.acceptance_moves, material_values, thresholds, mover)
        for trace in traces
    )
    if not evaluated:
        return None
    return min(evaluated, key=_defender_best_key)


def _best_left_hanging_line(  # noqa: PLR0913, PLR0917 - explicit line inputs aid auditability
    board: BoardService,
    root: PositionSnapshot,
    after_candidate: PositionSnapshot,
    candidate: Move,
    acceptance_moves: tuple[str, ...],
    material_values: MaterialValues,
    thresholds: SacrificeThresholds,
    mover: Color,
) -> _EvaluatedLine | None:
    traces: list[ExchangeTrace] = []
    for acceptance in acceptance_moves:
        nested = board.exchange_lines(
            after_candidate.position.fen,
            (),
            acceptance,
            max_plies=max(1, thresholds.exchange_search_plies - 1),
        )
        traces.extend(nested)
    if not traces:
        return None
    evaluated: list[_EvaluatedLine] = []
    for trace in traces:
        first = _candidate_as_ply(trace)
        evaluated.append(
            _evaluate_trace(
                ExchangeTrace(
                    root=root,
                    after_candidate=after_candidate,
                    target_square=trace.target_square,
                    candidate=candidate,
                    acceptance_moves=(first, *trace.acceptance_moves),
                ),
                (first, *trace.acceptance_moves),
                material_values,
                thresholds,
                mover,
            )
        )
    return min(evaluated, key=_defender_best_key)


def _defender_best_key(line: _EvaluatedLine) -> tuple[float, int, tuple[str, ...]]:
    """Prefer the greatest concession, shortest line, then lowest UCI line."""
    return (-line.net_material_concession, len(line.acceptance_moves), line.sequence_uci)


def _candidate_as_ply(trace: ExchangeTrace) -> ExchangePly:
    return ExchangePly(
        before=trace.root,
        move=trace.candidate,
        after=trace.after_candidate,
        captured_piece=_captured_piece(
            trace.root, trace.after_candidate, trace.root.position.side_to_move
        ),
    )


def _evaluate_trace(
    trace: ExchangeTrace,
    acceptance_moves: tuple[ExchangePly, ...],
    material_values: MaterialValues,
    thresholds: SacrificeThresholds,
    mover: Color,
) -> _EvaluatedLine:
    material_before = material_balance(trace.root.placement, mover, material_values)
    material_immediately_after = material_balance(
        trace.after_candidate.placement,
        mover,
        material_values,
    )
    final_snapshot = acceptance_moves[-1].after if acceptance_moves else trace.after_candidate
    material_after_best_acceptance = material_balance(
        final_snapshot.placement,
        mover,
        material_values,
    )
    material_captured_by_candidate = _captured_value(
        trace.root,
        trace.after_candidate,
        mover.opponent,
        material_values,
    )
    material_lost_by_mover = sum(
        material_values.value_of(step.captured_piece.piece_type)
        for step in acceptance_moves
        if step.captured_piece is not None and step.captured_piece.color is mover
    )
    material_captured_later_by_mover = sum(
        material_values.value_of(step.captured_piece.piece_type)
        for step in acceptance_moves
        if step.captured_piece is not None
        and step.captured_piece.color is mover.opponent
        and step.before.position.side_to_move is mover
    )
    total_captured = material_captured_by_candidate + material_captured_later_by_mover
    net_material_concession = max(0.0, material_lost_by_mover - total_captured)
    clean_trade = (
        bool(acceptance_moves)
        and abs(material_after_best_acceptance - material_before)
        <= thresholds.equal_trade_tolerance
    )
    favorable_trade = material_after_best_acceptance > (
        material_before + thresholds.equal_trade_tolerance
    )
    obvious_recapture = (
        material_captured_by_candidate > 0.0
        and len(acceptance_moves) == 1
        and acceptance_moves[0].before.position.side_to_move is mover.opponent
    )
    temporary_offer = (
        material_captured_by_candidate == 0.0 and material_captured_later_by_mover > 0.0
    )
    xray_recapture = material_captured_by_candidate > 0.0 and material_captured_later_by_mover > 0.0
    return _EvaluatedLine(
        trace=trace,
        acceptance_moves=acceptance_moves,
        material_before=material_before,
        material_immediately_after=material_immediately_after,
        material_after_best_acceptance=material_after_best_acceptance,
        material_captured_by_candidate=material_captured_by_candidate,
        material_lost_by_mover=material_lost_by_mover,
        material_captured_later_by_mover=material_captured_later_by_mover,
        net_material_concession=net_material_concession,
        sequence_uci=(trace.candidate.uci, *(step.move.uci for step in acceptance_moves)),
        sequence_san=(
            trace.candidate.san or trace.candidate.uci,
            *(step.move.san or step.move.uci for step in acceptance_moves),
        ),
        clean_trade=clean_trade,
        obvious_recapture=obvious_recapture,
        temporary_offer=temporary_offer,
        favorable_trade=favorable_trade,
        xray_recapture=xray_recapture,
    )


def _destination_result(
    offer: SacrificeEvidence,
    line: _EvaluatedLine,
    thresholds: SacrificeThresholds,
) -> SacrificeEvidence:
    disposition = _destination_disposition(line, thresholds)
    return _build_result(
        offer=offer,
        line=line,
        thresholds=thresholds,
        disposition=disposition,
        kind=_kind_for(disposition, line, thresholds),
    )


def _left_hanging_result(
    offer: SacrificeEvidence,
    line: _EvaluatedLine,
    thresholds: SacrificeThresholds,
) -> SacrificeEvidence:
    disposition = ExchangeDisposition.LEFT_HANGING
    return _build_result(
        offer=offer,
        line=line,
        thresholds=thresholds,
        disposition=disposition,
        kind=_kind_for(disposition, line, thresholds),
    )


def _destination_disposition(  # noqa: PLR0911 - ordered dispositions are explicit policy
    line: _EvaluatedLine,
    thresholds: SacrificeThresholds,
) -> ExchangeDisposition:
    if line.clean_trade:
        return ExchangeDisposition.CLEAN_EQUAL_TRADE
    if line.favorable_trade:
        return ExchangeDisposition.FAVORABLE_TRADE
    if line.temporary_offer:
        return ExchangeDisposition.TEMPORARY_OFFER
    if (
        line.obvious_recapture
        and line.net_material_concession < thresholds.min_net_material_concession
    ):
        return ExchangeDisposition.OBVIOUS_RECAPTURE
    if (
        line.xray_recapture
        and line.net_material_concession >= thresholds.min_net_material_concession
    ):
        return ExchangeDisposition.CLEARANCE_OR_DEFLECTION
    if line.material_captured_by_candidate > 0.0 and (
        line.net_material_concession >= thresholds.min_net_material_concession
    ):
        return ExchangeDisposition.EXCHANGE_SACRIFICE
    return ExchangeDisposition.DESTINATION_OFFER


def _kind_for(
    disposition: ExchangeDisposition,
    line: _EvaluatedLine,
    thresholds: SacrificeThresholds,
) -> SacrificeKind | None:
    if line.net_material_concession < thresholds.min_net_material_concession:
        return None
    return {
        ExchangeDisposition.DESTINATION_OFFER: SacrificeKind.DESTINATION_OFFER,
        ExchangeDisposition.LEFT_HANGING: SacrificeKind.LEFT_HANGING,
        ExchangeDisposition.EXCHANGE_SACRIFICE: SacrificeKind.EXCHANGE_SACRIFICE,
        ExchangeDisposition.CLEARANCE_OR_DEFLECTION: SacrificeKind.CLEARANCE_OR_DEFLECTION,
        ExchangeDisposition.DECLINED_RECAPTURE: SacrificeKind.DECLINED_RECAPTURE,
    }.get(disposition)


def _build_result(
    *,
    offer: SacrificeEvidence,
    line: _EvaluatedLine,
    thresholds: SacrificeThresholds,
    disposition: ExchangeDisposition,
    kind: SacrificeKind | None,
) -> SacrificeEvidence:
    exchange = ExchangeEvidence(
        disposition=disposition,
        material_before=line.material_before,
        material_immediately_after=line.material_immediately_after,
        material_after_best_acceptance=line.material_after_best_acceptance,
        material_captured_by_candidate=line.material_captured_by_candidate,
        material_lost_by_mover=line.material_lost_by_mover,
        material_captured_later_by_mover=line.material_captured_later_by_mover,
        net_material_concession=line.net_material_concession,
        sequence_uci=line.sequence_uci,
        sequence_san=line.sequence_san,
        clean_trade=line.clean_trade,
        obvious_recapture=line.obvious_recapture,
        temporary_offer=line.temporary_offer,
        favorable_trade=line.favorable_trade,
        xray_recapture=line.xray_recapture,
        trace=line.trace,
    )
    signals = SacrificeSignals(
        legal_capture_available=bool(offer.acceptance_moves),
        material_deficit_in_acceptance=line.net_material_concession
        >= thresholds.min_net_material_concession,
        tactical_mechanism_in_pv=line.xray_recapture,
    )
    reasons = _exchange_reasons(
        exchange,
        signals,
        line.net_material_concession >= thresholds.min_net_material_concession,
    )
    return SacrificeEvidence(
        detected=kind is not None,
        kind=kind,
        exchange=exchange,
        offered_piece_square=offer.offered_piece_square,
        offered_piece_type=offer.offered_piece_type,
        nominal_value=offer.nominal_value,
        acceptance_moves=offer.acceptance_moves,
        material_trajectory=(
            line.material_before,
            line.material_immediately_after,
            line.material_after_best_acceptance,
        ),
        confidence=sacrifice_confidence(signals, thresholds.confidence_weights),
        reasons=reasons,
        signals=signals,
    )


def _exchange_reasons(
    exchange: ExchangeEvidence,
    signals: SacrificeSignals,
    passed_threshold: bool,
) -> tuple[ReasonCode, ...]:
    reasons = list(reasons_for(signals))
    if exchange.clean_trade:
        reasons.append(ReasonCode.EQUAL_EXCHANGE)
    if exchange.favorable_trade:
        reasons.append(ReasonCode.FAVORABLE_EXCHANGE)
    if exchange.obvious_recapture:
        reasons.append(ReasonCode.OBVIOUS_RECAPTURE)
    if exchange.temporary_offer:
        reasons.append(ReasonCode.RECOVERED_MATERIAL)
    if passed_threshold:
        reasons.append(ReasonCode.NET_MATERIAL_CONCESSION)
    if exchange.xray_recapture:
        reasons.append(ReasonCode.XRAY_RECAPTURE)
    return tuple(dict.fromkeys(reasons)) if reasons else _EMPTY_REASONS


def _captured_value(
    before: PositionSnapshot,
    after: PositionSnapshot,
    victim: Color,
    material_values: MaterialValues,
) -> float:
    return sum(
        material_values.value_of(piece.piece_type)
        for square, piece in before.placement.items()
        if piece.color is victim
        and piece.piece_type is not PieceType.KING
        and (
            (after_piece := after.placement.get(square)) is None
            or after_piece.color is not piece.color
            or after_piece.piece_type is not piece.piece_type
        )
    )


def _captured_piece(
    before: PositionSnapshot,
    after: PositionSnapshot,
    mover: Color,
) -> Piece | None:
    removed = [
        piece
        for square, piece in before.placement.items()
        if piece.color is mover.opponent
        and (
            (after_piece := after.placement.get(square)) is None
            or after_piece.color is mover
            or after_piece.piece_type is not piece.piece_type
        )
    ]
    return removed[0] if removed else None
