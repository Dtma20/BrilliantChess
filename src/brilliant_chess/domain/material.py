"""Contagem material pura sobre snapshots de posicao.

O dominio nao le tabuleiros: um adapter converte a posicao em ``PiecePlacement``
(ver ADR 0004). Assim promocao, en passant e roque sao resolvidos por
python-chess no adapter e a aritmetica aqui permanece testavel sem motor.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.values import Color, PieceType


@dataclass(frozen=True)
class Piece:
    color: Color
    piece_type: PieceType


#: Casa em notacao algebrica ("e4") -> peca ocupante.
type PiecePlacement = Mapping[str, Piece]

#: Pecas que satisfazem GATE_SACRIFICE_001 em strict_v1 (peao sozinho nao basta).
SACRIFICEABLE_PIECES: Final[frozenset[PieceType]] = frozenset(
    {PieceType.KNIGHT, PieceType.BISHOP, PieceType.ROOK, PieceType.QUEEN}
)


@dataclass(frozen=True)
class MaterialValues:
    """Valores nominais configuraveis. Servem para detectar concessao material.

    A correcao da jogada vem do motor, nunca desta tabela.
    """

    pawn: float = 1.0
    knight: float = 3.2
    bishop: float = 3.3
    rook: float = 5.0
    queen: float = 9.0

    def value_of(self, piece_type: PieceType) -> float:
        if piece_type is PieceType.KING:
            raise DomainError("O rei nao tem valor material mensuravel")
        return {
            PieceType.PAWN: self.pawn,
            PieceType.KNIGHT: self.knight,
            PieceType.BISHOP: self.bishop,
            PieceType.ROOK: self.rook,
            PieceType.QUEEN: self.queen,
        }[piece_type]


DEFAULT_MATERIAL_VALUES: Final[MaterialValues] = MaterialValues()


def material_for(
    placement: PiecePlacement,
    color: Color,
    values: MaterialValues = DEFAULT_MATERIAL_VALUES,
) -> float:
    """Soma o material de uma cor. Reis sao ignorados."""
    return sum(
        values.value_of(piece.piece_type)
        for piece in placement.values()
        if piece.color is color and piece.piece_type is not PieceType.KING
    )


def material_balance(
    placement: PiecePlacement,
    color: Color,
    values: MaterialValues = DEFAULT_MATERIAL_VALUES,
) -> float:
    """Material proprio menos material adversario, do ponto de vista de ``color``."""
    return material_for(placement, color, values) - material_for(placement, color.opponent, values)


def material_delta(
    before: PiecePlacement,
    after: PiecePlacement,
    color: Color,
    values: MaterialValues = DEFAULT_MATERIAL_VALUES,
) -> float:
    """Variacao do balanco material de ``color`` entre dois snapshots.

    Negativo significa material concedido. Promocao aparece como o ganho da peca
    promovida menos o peao; en passant aparece como remocao do peao capturado.
    """
    return material_balance(after, color, values) - material_balance(before, color, values)


def is_sacrificeable(piece_type: PieceType) -> bool:
    """strict_v1: apenas cavalo, bispo, torre e dama contam como sacrificio de peca."""
    return piece_type in SACRIFICEABLE_PIECES
