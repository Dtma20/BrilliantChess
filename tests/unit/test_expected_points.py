from __future__ import annotations

import pytest

from brilliant_chess.domain.errors import InvalidEvaluationError
from brilliant_chess.domain.expected_points import (
    NON_MATE_EP_CEILING,
    NON_MATE_EP_FLOOR,
    clamp_expected_points,
    expected_points_from_centipawns,
    expected_points_from_mate,
    expected_points_from_wdl,
    expected_points_loss,
    flip_expected_points,
    flip_wdl,
)


def test_wdl_to_expected_points_uses_half_draw():
    assert expected_points_from_wdl((600, 200, 200)) == pytest.approx(0.7)


def test_wdl_all_draws_is_half():
    assert expected_points_from_wdl((0, 1000, 0)) == pytest.approx(0.5)


def test_wdl_rejects_negative_and_empty():
    with pytest.raises(InvalidEvaluationError):
        expected_points_from_wdl((-1, 0, 1))
    with pytest.raises(InvalidEvaluationError):
        expected_points_from_wdl((0, 0, 0))


def test_centipawn_fallback_is_monotonic_and_centered():
    assert expected_points_from_centipawns(0) == pytest.approx(0.5)
    values = [expected_points_from_centipawns(cp) for cp in (-800, -100, 0, 100, 800)]
    assert values == sorted(values)


def test_extreme_scores_stay_inside_non_mate_band():
    assert expected_points_from_centipawns(100_000) <= NON_MATE_EP_CEILING
    assert expected_points_from_centipawns(-100_000) >= NON_MATE_EP_FLOOR
    assert expected_points_from_wdl((1000, 0, 0)) <= NON_MATE_EP_CEILING


def test_mate_for_beats_every_non_mate_score():
    assert expected_points_from_mate(1) > expected_points_from_centipawns(100_000)
    assert expected_points_from_mate(1) > expected_points_from_wdl((1000, 0, 0))


def test_mate_against_is_worse_than_every_non_mate_score():
    assert expected_points_from_mate(-1) < expected_points_from_centipawns(-100_000)


def test_shorter_mate_is_preferred_only_as_tiebreak():
    assert expected_points_from_mate(1) > expected_points_from_mate(9)
    assert expected_points_from_mate(1) - expected_points_from_mate(9) < 1e-3


def test_mate_zero_is_ambiguous():
    with pytest.raises(InvalidEvaluationError):
        expected_points_from_mate(0)


def test_flip_expected_points_is_involutive():
    assert flip_expected_points(flip_expected_points(0.31)) == pytest.approx(0.31)
    assert flip_wdl(flip_wdl((10, 20, 30))) == (10, 20, 30)


def test_expected_points_loss_is_never_negative_after_noise():
    result = expected_points_loss(0.700000, 0.7000001)
    assert result.value == 0.0
    assert result.clamped_noise is True
    assert result.raw_difference < 0.0


def test_expected_points_loss_reports_real_difference():
    result = expected_points_loss(0.72, 0.70)
    assert result.value == pytest.approx(0.02)
    assert result.clamped_noise is False


def test_candidate_above_best_beyond_tolerance_is_an_error():
    with pytest.raises(InvalidEvaluationError):
        expected_points_loss(0.50, 0.90)


def test_clamp_rejects_nan():
    with pytest.raises(InvalidEvaluationError):
        clamp_expected_points(float("nan"))
