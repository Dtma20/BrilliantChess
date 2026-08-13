from __future__ import annotations

import pytest

from brilliant_chess.domain.errors import (
    DomainError,
    InvalidEvaluationError,
    InvalidFenError,
    InvalidMoveError,
)
from brilliant_chess.domain.models import (
    AnalysisBudget,
    Move,
    NormalizedEvaluation,
    Position,
    PrincipalVariation,
)
from brilliant_chess.domain.values import Color
from tests.conftest import BLACK_TO_MOVE_FEN, STARTPOS


def test_position_from_fen_derives_side_to_move():
    assert Position.from_fen(STARTPOS).side_to_move is Color.WHITE
    assert Position.from_fen(BLACK_TO_MOVE_FEN).side_to_move is Color.BLACK


@pytest.mark.parametrize(
    "fen",
    [
        "8/8/8/8 w - -",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
        "rnbqkbnr/pppppppp/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    ],
)
def test_invalid_fen_raises_domain_error(fen):
    with pytest.raises(InvalidFenError):
        Position.from_fen(fen)


def test_position_rejects_side_mismatch():
    with pytest.raises(InvalidFenError):
        Position(fen=STARTPOS, side_to_move=Color.BLACK)


def test_move_requires_uci_length():
    assert Move("e2e4").uci == "e2e4"
    assert Move("a7a8q").uci == "a7a8q"
    with pytest.raises(InvalidMoveError):
        Move("e2")


def test_budget_requires_at_least_one_limit():
    with pytest.raises(DomainError):
        AnalysisBudget()


def test_node_budget_is_deterministic_and_time_budget_is_not():
    assert AnalysisBudget(nodes=1000).is_deterministic is True
    assert AnalysisBudget(time_seconds=1.0).is_deterministic is False


@pytest.mark.parametrize("mover", [Color.WHITE, Color.BLACK])
def test_point_of_view_flip_is_consistent_for_both_colors(mover):
    original = NormalizedEvaluation.create(mover=mover, centipawns=150, wdl=(700, 200, 100))
    flipped = original.flipped()
    assert flipped.mover is mover.opponent
    assert flipped.centipawns == -150
    assert flipped.wdl == (100, 200, 700)
    assert flipped.expected_points == pytest.approx(1.0 - original.expected_points)


def test_flip_preserves_mate_direction():
    mate_for_white = NormalizedEvaluation.create(mover=Color.WHITE, mate_in=3)
    mate_against_black = mate_for_white.flipped()
    assert mate_against_black.mate_in == -3
    assert mate_against_black.expected_points < 0.01


def test_evaluation_prefers_mate_over_wdl_and_centipawns():
    evaluation = NormalizedEvaluation.create(
        mover=Color.WHITE, centipawns=200, mate_in=2, wdl=(500, 300, 200)
    )
    assert evaluation.is_mate is True
    assert evaluation.expected_points > 0.999


def test_evaluation_requires_some_score():
    with pytest.raises(InvalidEvaluationError):
        NormalizedEvaluation.create(mover=Color.WHITE)


def test_expected_points_outside_range_is_rejected():
    with pytest.raises(InvalidEvaluationError):
        NormalizedEvaluation(mover=Color.WHITE, centipawns=10, mate_in=None, expected_points=1.5)


def test_pv_overlap_counts_only_the_common_prefix():
    first = PrincipalVariation(moves_uci=("h5h7", "g8h7", "d1h5"))
    second = PrincipalVariation(moves_uci=("h5h7", "g8h7", "f3g5"))
    assert first.overlap_plies(second) == 2
    assert first.overlap_plies(PrincipalVariation(moves_uci=("e2e4",))) == 0
