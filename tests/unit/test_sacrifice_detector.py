from __future__ import annotations

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application.sacrifice_detector import (
    detect_destination_offer,
    detect_left_hanging,
    detect_sacrifice,
)
from brilliant_chess.domain.material import MaterialValues
from brilliant_chess.domain.sacrifice import NO_SACRIFICE
from brilliant_chess.domain.values import PieceType, SacrificeKind

#: Posicao apos 13...Bf5 na partida do relatorio: a torre de b1 ja esta sob
#: ataque pela diagonal f5-e4-d3-c2-b1, e 14.e3 nao a salva nem a defende.
LEFT_HANGING_ROOK_FEN = "r2qkb1r/1p3p1p/5np1/3Ppb2/7Q/p1N2N2/PP2PPPP/1RB1KB1R w Kkq - 2 14"


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


def test_detects_the_rook_left_hanging_on_b1_after_e3():
    board = PythonChessBoardService()
    position = board.position_after(LEFT_HANGING_ROOK_FEN, ())

    evidence = detect_left_hanging(board, position, "e2e3", material_values=MaterialValues())

    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"
    assert evidence.offered_piece_type is PieceType.ROOK
    assert evidence.nominal_value == 5.0
    assert evidence.acceptance_moves == ("f5b1",)


def test_detects_a_piece_newly_exposed_by_the_candidate():
    board = PythonChessBoardService()
    position = board.position_after("7k/8/8/5b2/8/8/3N4/1R4K1 w - - 0 1", ())

    evidence = detect_left_hanging(board, position, "d2f3", material_values=MaterialValues())

    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"
    assert evidence.acceptance_moves == ("f5b1",)


def test_ignores_a_piece_behind_a_blocked_diagonal():
    board = PythonChessBoardService()
    position = board.position_after("7k/8/8/5b2/8/8/2P5/1R5K w - - 0 1", ())

    assert (
        detect_left_hanging(board, position, "h1h2", material_values=MaterialValues())
        == NO_SACRIFICE
    )


def test_ignores_an_attacker_that_is_pinned_and_cannot_capture():
    board = PythonChessBoardService()
    position = board.position_after("5k2/8/8/5b2/8/8/8/1R3R1K w - - 0 1", ())

    assert (
        detect_left_hanging(board, position, "h1h2", material_values=MaterialValues())
        == NO_SACRIFICE
    )


def test_a_hanging_pawn_is_never_the_offered_piece():
    board = PythonChessBoardService()
    position = board.position_after("7k/8/8/5b2/4P3/8/8/6K1 w - - 0 1", ())

    assert (
        detect_left_hanging(board, position, "g1h2", material_values=MaterialValues())
        == NO_SACRIFICE
    )


def test_picks_the_most_valuable_piece_among_several_hanging_ones():
    board = PythonChessBoardService()
    position = board.position_after("7k/8/8/5b2/3p4/2N5/8/1R4K1 w - - 0 1", ())

    evidence = detect_left_hanging(board, position, "g1h2", material_values=MaterialValues())

    assert evidence.offered_piece_square == "b1"
    assert evidence.offered_piece_type is PieceType.ROOK
    assert evidence.acceptance_moves == ("f5b1",)


def test_the_destination_offer_wins_when_both_kinds_are_present():
    board = PythonChessBoardService()
    position = board.position_after("k6r/7p/8/5b1Q/8/8/8/1R4K1 w - - 0 1", ())

    evidence = detect_sacrifice(board, position, "h5h7", material_values=MaterialValues())

    assert evidence.kind is SacrificeKind.DESTINATION_OFFER
    assert evidence.offered_piece_square == "h7"
    assert evidence.acceptance_moves == ("f5h7", "h8h7")


def test_the_combined_detector_falls_back_to_left_hanging():
    board = PythonChessBoardService()
    position = board.position_after(LEFT_HANGING_ROOK_FEN, ())

    evidence = detect_sacrifice(board, position, "e2e3", material_values=MaterialValues())

    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"


def test_the_offered_piece_on_the_destination_square_is_not_counted_twice():
    """A casa de destino pertence a ``DESTINATION_OFFER``; os tipos nao se sobrepoem."""
    board = PythonChessBoardService()
    position = board.position_after("k6r/7p/8/7Q/8/8/8/6K1 w - - 0 1", ())

    assert (
        detect_left_hanging(board, position, "h5h7", material_values=MaterialValues())
        == NO_SACRIFICE
    )
