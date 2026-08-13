from __future__ import annotations

import pytest

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.material import (
    DEFAULT_MATERIAL_VALUES,
    Piece,
    is_sacrificeable,
    material_balance,
    material_delta,
    material_for,
)
from brilliant_chess.domain.values import Color, PieceType

WHITE_KING = Piece(Color.WHITE, PieceType.KING)
BLACK_KING = Piece(Color.BLACK, PieceType.KING)


def placement(**pieces: Piece) -> dict[str, Piece]:
    return {"e1": WHITE_KING, "e8": BLACK_KING, **pieces}


def test_king_has_no_measurable_value():
    with pytest.raises(DomainError):
        DEFAULT_MATERIAL_VALUES.value_of(PieceType.KING)


def test_material_for_ignores_kings():
    board = placement(a1=Piece(Color.WHITE, PieceType.ROOK))
    assert material_for(board, Color.WHITE) == pytest.approx(5.0)
    assert material_for(board, Color.BLACK) == pytest.approx(0.0)


def test_balance_is_symmetric_between_colors():
    board = placement(
        a1=Piece(Color.WHITE, PieceType.ROOK), a8=Piece(Color.BLACK, PieceType.KNIGHT)
    )
    assert material_balance(board, Color.WHITE) == pytest.approx(
        -material_balance(board, Color.BLACK)
    )


def test_capture_changes_balance_by_captured_value():
    before = placement(
        c1=Piece(Color.WHITE, PieceType.BISHOP), b8=Piece(Color.BLACK, PieceType.KNIGHT)
    )
    after = placement(b8=Piece(Color.WHITE, PieceType.BISHOP))
    assert material_delta(before, after, Color.WHITE) == pytest.approx(3.2)


def test_en_passant_removes_the_captured_pawn():
    before = placement(e5=Piece(Color.WHITE, PieceType.PAWN), d5=Piece(Color.BLACK, PieceType.PAWN))
    after = placement(d6=Piece(Color.WHITE, PieceType.PAWN))
    assert material_delta(before, after, Color.WHITE) == pytest.approx(1.0)


def test_promotion_replaces_pawn_value_with_promoted_piece():
    before = placement(a7=Piece(Color.WHITE, PieceType.PAWN))
    after = placement(a8=Piece(Color.WHITE, PieceType.QUEEN))
    assert material_delta(before, after, Color.WHITE) == pytest.approx(8.0)


def test_underpromotion_uses_the_chosen_piece_value():
    before = placement(a7=Piece(Color.WHITE, PieceType.PAWN))
    after = placement(a8=Piece(Color.WHITE, PieceType.KNIGHT))
    assert material_delta(before, after, Color.WHITE) == pytest.approx(2.2)


def test_castling_is_not_a_rook_sacrifice():
    before = {"e1": WHITE_KING, "h1": Piece(Color.WHITE, PieceType.ROOK), "e8": BLACK_KING}
    after = {"g1": WHITE_KING, "f1": Piece(Color.WHITE, PieceType.ROOK), "e8": BLACK_KING}
    assert material_delta(before, after, Color.WHITE) == pytest.approx(0.0)


def test_equal_exchange_leaves_balance_unchanged():
    before = placement(
        d4=Piece(Color.WHITE, PieceType.KNIGHT), d5=Piece(Color.BLACK, PieceType.KNIGHT)
    )
    after = placement(d5=Piece(Color.BLACK, PieceType.KNIGHT))
    assert material_delta(before, after, Color.WHITE) == pytest.approx(-3.2)


@pytest.mark.parametrize(
    ("piece_type", "expected"),
    [
        (PieceType.PAWN, False),
        (PieceType.KNIGHT, True),
        (PieceType.BISHOP, True),
        (PieceType.ROOK, True),
        (PieceType.QUEEN, True),
        (PieceType.KING, False),
    ],
)
def test_only_pieces_qualify_for_strict_v1_sacrifice(piece_type, expected):
    assert is_sacrificeable(piece_type) is expected
