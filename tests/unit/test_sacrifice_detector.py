from __future__ import annotations

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application.sacrifice_detector import detect_destination_offer
from brilliant_chess.domain.material import MaterialValues
from brilliant_chess.domain.sacrifice import NO_SACRIFICE
from brilliant_chess.domain.values import PieceType, SacrificeKind


def test_returns_no_sacrifice_when_no_piece_is_offered():
    board = PythonChessBoardService()
    position = board.position_after("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", ())

    assert (
        detect_destination_offer(board, position, "g1f3", material_values=MaterialValues())
        == NO_SACRIFICE
    )


def test_rejects_a_capturable_pawn_offer():
    board = PythonChessBoardService()
    position = board.position_after("7k/8/8/3p4/8/4P3/8/7K w - - 0 1", ())

    assert (
        detect_destination_offer(board, position, "e3e4", material_values=MaterialValues())
        == NO_SACRIFICE
    )


def test_detects_a_capturable_non_pawn_offer_with_configured_material_value():
    board = PythonChessBoardService()
    position = board.position_after("7r/7p/8/7Q/8/8/8/6KR w - - 0 1", ())

    evidence = detect_destination_offer(
        board,
        position,
        "h5h7",
        material_values=MaterialValues(queen=8.5),
    )

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.DESTINATION_OFFER
    assert evidence.offered_piece_type is PieceType.QUEEN
    assert evidence.nominal_value == 8.5
    assert evidence.acceptance_moves == ("h8h7",)
    assert evidence.signals.legal_capture_available is True
