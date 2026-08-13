from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application import play_game
from brilliant_chess.domain.values import Color, GameStatus
from brilliant_chess.interfaces.web.pgn import build_pgn

BLACK_TO_MOVE_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def state_with_moves(board, initial_fen, human_color, moves):
    state = play_game.start_game("teste", initial_fen, human_color, "clube")
    view = board.view(initial_fen, moves)
    return replace(state, moves_uci=moves, moves_san=view.moves_san)


def test_build_pgn_has_headers_and_standard_movetext(board):
    state = state_with_moves(board, STARTING_FEN, Color.WHITE, ("e2e4", "e7e5"))
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Event "Brilliant Chess - Partida local"]' in pgn
    assert '[White "Voce"]' in pgn
    assert '[Black "Motor (Clube (~1900))"]' in pgn
    assert '[Result "*"]' in pgn
    assert "1. e4 e5 *" in pgn
    assert pgn.endswith("\n")


def test_build_pgn_numbers_black_moves_after_each_full_move(board):
    moves = ("e2e4", "e7e5", "g1f3", "d7d6")
    state = state_with_moves(board, STARTING_FEN, Color.WHITE, moves)
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, moves)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert "1. e4 e5 2. Nf3 d6 *" in pgn


def test_build_pgn_uses_black_ellipsis_for_black_to_move(board):
    state = state_with_moves(board, BLACK_TO_MOVE_FEN, Color.WHITE, ("e7e5",))
    initial = board.view(BLACK_TO_MOVE_FEN, ())
    current = board.view(BLACK_TO_MOVE_FEN, state.moves_uci)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert "1... e5 *" in pgn


def test_build_pgn_includes_setup_headers_for_custom_fen(board):
    custom_fen = "8/5k2/8/8/8/8/8/R5K1 b - - 0 12"
    state = state_with_moves(board, custom_fen, Color.WHITE, ())
    initial = board.view(custom_fen, ())

    pgn = build_pgn(state, initial, initial, standard_fen=STARTING_FEN)

    assert '[SetUp "1"]' in pgn
    assert f'[FEN "{custom_fen}"]' in pgn
    assert '[Result "*"]' in pgn


def test_build_pgn_maps_checkmate_to_result(board):
    moves = ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    state = state_with_moves(board, STARTING_FEN, Color.WHITE, moves)
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, moves)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Result "1-0"]' in pgn
    assert pgn.rstrip().endswith("1-0")


def test_build_pgn_maps_draw_to_result(board):
    initial = board.view("7k/5Q2/7K/8/8/8/8/8 b - - 0 1", ())
    state = state_with_moves(board, initial.position.fen, Color.WHITE, ())
    current = replace(initial, status=GameStatus.STALEMATE)

    pgn = build_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Result "1/2-1/2"]' in pgn
    assert pgn.rstrip().endswith("1/2-1/2")
