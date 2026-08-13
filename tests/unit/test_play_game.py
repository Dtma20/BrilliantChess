from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application import play_game
from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.strength import STRENGTH_LEVELS, strength_by_key
from brilliant_chess.domain.values import Color, GameStatus
from tests.fakes.fixed_engine import FixedEngine


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


@pytest.fixture
def engine() -> FixedEngine:
    return FixedEngine()


def new_game(color: Color = Color.WHITE) -> play_game.GameState:
    return play_game.start_game("teste", STARTING_FEN, color, "clube")


def test_unknown_strength_is_rejected():
    with pytest.raises(DomainError):
        play_game.start_game("teste", STARTING_FEN, Color.WHITE, "impossivel")


def test_every_preset_strength_is_resolvable():
    for level in STRENGTH_LEVELS:
        assert strength_by_key(level.key) is level


def test_white_human_moves_first(board):
    state = new_game(Color.WHITE)
    assert play_game.is_engine_turn(board, state) is False
    state = play_game.play_human_move(board, state, "e4")
    assert state.moves_uci == ("e2e4",)
    assert state.moves_san == ("e4",)
    assert play_game.is_engine_turn(board, state) is True


def test_black_human_lets_the_engine_open(board, engine):
    state = new_game(Color.BLACK)
    assert play_game.is_engine_turn(board, state) is True
    state = play_game.play_engine_move(board, engine, state)
    assert len(state.moves_uci) == 1
    assert play_game.is_engine_turn(board, state) is False


def test_playing_out_of_turn_is_rejected(board, engine):
    state = new_game(Color.WHITE)
    with pytest.raises(DomainError):
        play_game.play_engine_move(board, engine, state)
    state = play_game.play_human_move(board, state, "e4")
    with pytest.raises(DomainError):
        play_game.play_human_move(board, state, "e5")


def test_engine_receives_the_configured_strength(board, engine):
    state = play_game.start_game("teste", STARTING_FEN, Color.BLACK, "iniciante")
    play_game.play_engine_move(board, engine, state)
    assert engine.calls[0][1] == "iniciante"


def test_undo_returns_the_turn_to_the_human(board, engine):
    state = new_game(Color.WHITE)
    state = play_game.play_human_move(board, state, "e4")
    state = play_game.play_engine_move(board, engine, state)
    assert len(state.moves_uci) == 2
    state = play_game.undo_full_move(board, state)
    assert state.moves_uci == ()
    assert play_game.is_engine_turn(board, state) is False


def test_undo_on_an_empty_game_is_a_no_op(board):
    state = new_game()
    assert play_game.undo_full_move(board, state) == state


def test_finished_game_refuses_further_moves(board):
    mate = ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    state = replace(
        play_game.start_game("teste", STARTING_FEN, Color.WHITE, "clube"),
        moves_uci=mate,
        moves_san=board.view(STARTING_FEN, mate).moves_san,
    )
    view = play_game.current_view(board, state)
    assert view.status is GameStatus.CHECKMATE
    assert play_game.is_engine_turn(board, state) is False
    with pytest.raises(DomainError):
        play_game.play_human_move(board, state, "a7a6")


@pytest.mark.parametrize(
    ("status", "human", "expected"),
    [
        (GameStatus.CHECKMATE, Color.WHITE, "Voce perdeu por xeque-mate"),
        (GameStatus.CHECKMATE, Color.BLACK, "Voce venceu por xeque-mate"),
        (GameStatus.STALEMATE, Color.WHITE, "Empate por afogamento"),
        (GameStatus.IN_PROGRESS, Color.WHITE, "Partida em andamento"),
    ],
)
def test_result_text_uses_the_side_to_move_as_the_loser(status, human, expected):
    assert play_game.result_text(status, Color.WHITE, human) == expected
