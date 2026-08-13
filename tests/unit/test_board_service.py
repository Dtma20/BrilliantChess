from __future__ import annotations

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.domain.errors import IllegalMoveError, InvalidFenError, InvalidMoveError
from brilliant_chess.domain.models import Position
from brilliant_chess.domain.values import Color, GameStatus, PieceType

SCHOLARS_MATE = ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
STALEMATE_FEN = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def test_view_of_the_starting_position(board):
    view = board.view(STARTING_FEN, ())
    assert view.position.side_to_move is Color.WHITE
    assert len(view.legal_moves) == 20
    assert view.status is GameStatus.IN_PROGRESS
    assert view.is_check is False
    assert view.last_move_uci is None
    assert view.moves_san == ()


def test_moves_produce_san_and_advance_the_position(board):
    view = board.view(STARTING_FEN, ("e2e4", "c7c5"))
    assert view.moves_san == ("e4", "c5")
    assert view.position.side_to_move is Color.WHITE
    assert view.last_move_uci == "c7c5"
    assert view.move_number == 2


def test_checkmate_is_detected(board):
    view = board.view(STARTING_FEN, SCHOLARS_MATE)
    assert view.status is GameStatus.CHECKMATE
    assert view.status.is_finished is True
    assert view.is_check is True
    assert view.moves_san[-1] == "Qxf7#"


def test_stalemate_is_detected(board):
    view = board.view(STALEMATE_FEN, ())
    assert view.status is GameStatus.STALEMATE
    assert view.legal_moves == ()


def test_normalize_move_accepts_uci_and_san(board):
    position = Position.from_fen(STARTING_FEN)
    assert board.normalize_move(position, "e2e4").uci == "e2e4"
    assert board.normalize_move(position, "e4").uci == "e2e4"
    assert board.normalize_move(position, " Nf3 ").uci == "g1f3"


def test_normalize_move_rejects_illegal_and_invalid(board):
    position = Position.from_fen(STARTING_FEN)
    with pytest.raises(IllegalMoveError):
        board.normalize_move(position, "e2e5")
    with pytest.raises(InvalidMoveError):
        board.normalize_move(position, "jogada")
    with pytest.raises(InvalidMoveError):
        board.normalize_move(position, "")


def test_invalid_fen_is_a_domain_error(board):
    with pytest.raises(InvalidFenError):
        board.view("nao e uma fen", ())


def test_illegal_move_in_history_is_rejected(board):
    with pytest.raises(IllegalMoveError):
        board.view(STARTING_FEN, ("e2e4", "e2e4"))


def test_snapshot_reflects_en_passant_capture(board):
    """A contagem material do dominio depende deste snapshot estar correto."""
    view = board.view(STARTING_FEN, ("e2e4", "a7a6", "e4e5", "d7d5", "e5d6"))
    placement = view.snapshot.placement
    assert "d5" not in placement
    assert placement["d6"].piece_type is PieceType.PAWN
    assert placement["d6"].color is Color.WHITE


def test_snapshot_reflects_castling(board):
    view = board.view(STARTING_FEN, ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5", "e1g1"))
    placement = view.snapshot.placement
    assert placement["g1"].piece_type is PieceType.KING
    assert placement["f1"].piece_type is PieceType.ROOK
    assert "h1" not in placement


def test_promotion_requires_the_piece_suffix(board):
    fen = "8/P6k/8/8/8/8/7K/8 w - - 0 1"
    position = Position.from_fen(fen)
    promoted = board.normalize_move(position, "a7a8q")
    assert promoted.san == "a8=Q"
    view = board.view(fen, ("a7a8n",))
    assert view.snapshot.placement["a8"].piece_type is PieceType.KNIGHT


def test_pv_san_stops_at_the_first_illegal_move(board):
    position = Position.from_fen(STARTING_FEN)
    assert board.pv_san(position, ("e2e4", "e7e5", "g1f3")) == ("e4", "e5", "Nf3")
    assert board.pv_san(position, ("e2e4", "e2e4")) == ("e4",)


def test_position_after_matches_view(board):
    moves = ("e2e4", "c7c5", "g1f3")
    assert board.position_after(STARTING_FEN, moves) == board.view(STARTING_FEN, moves).position
