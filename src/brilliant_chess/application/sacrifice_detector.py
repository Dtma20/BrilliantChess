"""Deteccao de oferta de peca, usando somente o contrato de tabuleiro.

Dois tipos estao implementados e nao se sobrepoem:

``DESTINATION_OFFER``
    A candidata move uma peca nao-peao para uma casa que o adversario pode
    capturar legalmente. A oferta esta na casa de destino.

``LEFT_HANGING``
    A candidata deixa capturavel uma peca nao-peao que **nao** esta na casa de
    destino: seja porque a candidata a expos, seja porque ela ja estava sob
    ataque e a candidata escolheu nao salva-la nem defende-la.

Ambos usam apenas lances legais do adversario na posicao resultante, entao
linha bloqueada, peca cravada e xeque em curso nunca geram falso positivo.
Deteccao nao e brilhantismo: a compensacao vem da melhor defesa, da trajetoria
material, da PV e da estabilidade, medidas em ``choose_brilliant_move``.
"""

from __future__ import annotations

from dataclasses import dataclass

from brilliant_chess.domain.material import MaterialValues
from brilliant_chess.domain.models import Move, Position
from brilliant_chess.domain.rule_set import SacrificeConfidenceWeights
from brilliant_chess.domain.sacrifice import (
    NO_SACRIFICE,
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.values import Color, PieceType, SacrificeKind
from brilliant_chess.ports.board import BoardService, BoardView

#: Nem peao nem rei podem ser a peca oferecida em ``strict_v1``.
_NEVER_OFFERED = frozenset({PieceType.PAWN, PieceType.KING})


@dataclass(frozen=True)
class _Offer:
    """Uma peca do lado que jogou e as capturas legais que a aceitam."""

    square: str
    piece_type: PieceType
    nominal_value: float
    acceptance_moves: tuple[str, ...]


def detect_sacrifice(
    board: BoardService,
    position: Position,
    candidate_move: str,
    *,
    material_values: MaterialValues,
    confidence_weights: SacrificeConfidenceWeights | None = None,
) -> SacrificeEvidence:
    """Oferta na casa de destino primeiro; peca deixada pendurada em seguida.

    A ordem e fixa e nao depende do valor das pecas: uma peca colocada na casa
    de destino e a oferta mais direta que existe, e e a que o adversario tem de
    responder imediatamente.
    """
    move, after = _after(board, position, candidate_move)
    mover = position.side_to_move
    weights = confidence_weights or SacrificeConfidenceWeights()
    offer = _destination_offer(after, move, material_values) or _left_hanging(
        after, move, mover, material_values
    )
    if offer is None:
        return NO_SACRIFICE
    kind = (
        SacrificeKind.DESTINATION_OFFER
        if offer.square == _destination_of(move)
        else SacrificeKind.LEFT_HANGING
    )
    return _evidence(offer, kind, weights)


def detect_destination_offer(
    board: BoardService,
    position: Position,
    candidate_move: str,
    *,
    material_values: MaterialValues,
    confidence_weights: SacrificeConfidenceWeights | None = None,
) -> SacrificeEvidence:
    """Mede se a candidata deixa uma peca nao-peao capturavel no destino."""
    move, after = _after(board, position, candidate_move)
    offer = _destination_offer(after, move, material_values)
    if offer is None:
        return NO_SACRIFICE
    return _evidence(
        offer,
        SacrificeKind.DESTINATION_OFFER,
        confidence_weights or SacrificeConfidenceWeights(),
    )


def detect_left_hanging(
    board: BoardService,
    position: Position,
    candidate_move: str,
    *,
    material_values: MaterialValues,
    confidence_weights: SacrificeConfidenceWeights | None = None,
) -> SacrificeEvidence:
    """Mede se a candidata deixa capturavel uma peca fora da casa de destino."""
    move, after = _after(board, position, candidate_move)
    offer = _left_hanging(after, move, position.side_to_move, material_values)
    if offer is None:
        return NO_SACRIFICE
    return _evidence(
        offer,
        SacrificeKind.LEFT_HANGING,
        confidence_weights or SacrificeConfidenceWeights(),
    )


def _after(board: BoardService, position: Position, candidate_move: str) -> tuple[Move, BoardView]:
    move = board.normalize_move(position, candidate_move)
    return move, board.view(position.fen, (move.uci,))


def _destination_of(move: Move) -> str:
    return move.uci[2:4]


def _destination_offer(
    after: BoardView, move: Move, material_values: MaterialValues
) -> _Offer | None:
    destination = _destination_of(move)
    offered = after.snapshot.placement.get(destination)
    if offered is None or offered.piece_type in _NEVER_OFFERED:
        return None
    acceptances = _acceptances(after, destination)
    if not acceptances:
        return None
    return _Offer(
        square=destination,
        piece_type=offered.piece_type,
        nominal_value=material_values.value_of(offered.piece_type),
        acceptance_moves=acceptances,
    )


def _left_hanging(
    after: BoardView,
    move: Move,
    mover: Color,
    material_values: MaterialValues,
) -> _Offer | None:
    """Escolhe deterministicamente entre todas as pecas pendentes do lado que jogou.

    Ordem: maior valor nominal, depois a menor UCI de aceitacao, depois a casa.
    Sem essa ordem total, duas pecas de mesmo valor tornariam a auditoria
    irreproduzivel.
    """
    destination = _destination_of(move)
    offers = [
        offer
        for square, piece in sorted(after.snapshot.placement.items())
        if square != destination
        and piece.color is mover
        and piece.piece_type not in _NEVER_OFFERED
        and (offer := _offer_at(after, square, piece.piece_type, material_values)) is not None
    ]
    if not offers:
        return None
    return min(
        offers,
        key=lambda offer: (-offer.nominal_value, offer.acceptance_moves[0], offer.square),
    )


def _offer_at(
    after: BoardView,
    square: str,
    piece_type: PieceType,
    material_values: MaterialValues,
) -> _Offer | None:
    acceptances = _acceptances(after, square)
    if not acceptances:
        return None
    return _Offer(
        square=square,
        piece_type=piece_type,
        nominal_value=material_values.value_of(piece_type),
        acceptance_moves=acceptances,
    )


def _acceptances(after: BoardView, square: str) -> tuple[str, ...]:
    """Somente lances legais do adversario que terminam em ``square``."""
    return tuple(sorted(legal.uci for legal in after.legal_moves if legal.uci[2:4] == square))


def _evidence(
    offer: _Offer, kind: SacrificeKind, weights: SacrificeConfidenceWeights
) -> SacrificeEvidence:
    signals = SacrificeSignals(legal_capture_available=True)
    return SacrificeEvidence(
        detected=True,
        kind=kind,
        offered_piece_square=offer.square,
        offered_piece_type=offer.piece_type,
        nominal_value=offer.nominal_value,
        acceptance_moves=offer.acceptance_moves,
        confidence=sacrifice_confidence(signals, weights),
        reasons=reasons_for(signals),
        signals=signals,
    )
