"""Deteccao de oferta de peca na casa de destino, usando o contrato de tabuleiro."""

from __future__ import annotations

from brilliant_chess.domain.material import MaterialValues
from brilliant_chess.domain.models import Position
from brilliant_chess.domain.rule_set import SacrificeConfidenceWeights
from brilliant_chess.domain.sacrifice import (
    NO_SACRIFICE,
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.values import PieceType, SacrificeKind
from brilliant_chess.ports.board import BoardService


def detect_destination_offer(
    board: BoardService,
    position: Position,
    candidate_move: str,
    *,
    material_values: MaterialValues,
    confidence_weights: SacrificeConfidenceWeights | None = None,
) -> SacrificeEvidence:
    """Mede se a candidata deixa uma peca nao-peao capturavel no destino."""
    weights = confidence_weights or SacrificeConfidenceWeights()
    move = board.normalize_move(position, candidate_move)
    after = board.view(position.fen, (move.uci,))
    destination = move.uci[2:4]
    offered = after.snapshot.placement.get(destination)
    if offered is None or offered.piece_type in {PieceType.PAWN, PieceType.KING}:
        return NO_SACRIFICE

    acceptances = tuple(legal.uci for legal in after.legal_moves if legal.uci[2:4] == destination)
    if not acceptances:
        return NO_SACRIFICE

    signals = SacrificeSignals(legal_capture_available=True)
    return SacrificeEvidence(
        detected=True,
        kind=SacrificeKind.DESTINATION_OFFER,
        offered_piece_square=destination,
        offered_piece_type=offered.piece_type,
        nominal_value=material_values.value_of(offered.piece_type),
        acceptance_moves=acceptances,
        confidence=sacrifice_confidence(signals, weights),
        reasons=reasons_for(signals),
        signals=signals,
    )
