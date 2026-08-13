from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application.play_match import (
    MatchPolicy,
    MatchProfile,
    SelectionKind,
    can_step,
    current_view,
    record_move,
    result_text,
    start_match,
)
from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.models import Move
from brilliant_chess.domain.values import Color, GameStatus


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def test_match_records_one_legal_ply_with_audit(board):
    state = start_match(
        "m1",
        STARTING_FEN,
        MatchProfile("maximo", MatchPolicy.STRICT_V1),
        MatchProfile("iniciante", MatchPolicy.NORMAL),
        max_plies=200,
    )
    moved = record_move(board, state, Move("e2e4"), SelectionKind.STRICT_V1, audit=None)
    assert moved.moves_uci == ("e2e4",)
    assert moved.moves_san == ("e4",)
    assert moved.current_fen == board.view(STARTING_FEN, ("e2e4",)).position.fen
    assert moved.moves[0].selection is SelectionKind.STRICT_V1
    assert moved.moves[0].color is Color.WHITE


def test_two_hundredth_ply_finishes_as_experimental_draw(board):
    state = replace(
        start_match(
            "m2",
            STARTING_FEN,
            MatchProfile("maximo", MatchPolicy.NORMAL),
            MatchProfile("iniciante", MatchPolicy.NORMAL),
            max_plies=2,
        ),
        moves_uci=("e2e4",),
        moves_san=("e4",),
        current_fen=board.view(STARTING_FEN, ("e2e4",)).position.fen,
    )
    capped = record_move(board, state, Move("e7e5"), SelectionKind.NORMAL, audit=None)
    assert capped.is_finished(board) is True
    assert result_text(board, capped) == "Empate por limite experimental (100 lances)"
    assert can_step(board, capped) is False
    with pytest.raises(DomainError):
        record_move(board, capped, Move("g1f3"), SelectionKind.NORMAL, audit=None)


def test_start_match_rejects_invalid_strength_and_cap():
    with pytest.raises(DomainError):
        start_match(
            "bad-strength",
            STARTING_FEN,
            MatchProfile("unknown", MatchPolicy.NORMAL),
            MatchProfile("iniciante", MatchPolicy.NORMAL),
        )
    with pytest.raises(DomainError):
        start_match(
            "bad-cap",
            STARTING_FEN,
            MatchProfile("maximo", MatchPolicy.NORMAL),
            MatchProfile("iniciante", MatchPolicy.NORMAL),
            max_plies=0,
        )


def test_finished_board_rejects_further_move(board):
    mate = ("e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    state = replace(
        start_match(
            "mate",
            STARTING_FEN,
            MatchProfile("maximo", MatchPolicy.NORMAL),
            MatchProfile("iniciante", MatchPolicy.NORMAL),
        ),
        moves_uci=mate,
        moves_san=board.view(STARTING_FEN, mate).moves_san,
        current_fen=board.view(STARTING_FEN, mate).position.fen,
    )
    assert current_view(board, state).status is GameStatus.CHECKMATE
    assert state.is_finished(board)
    with pytest.raises(DomainError):
        record_move(board, state, Move("a7a6"), SelectionKind.NORMAL, audit=None)
