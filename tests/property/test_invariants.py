from __future__ import annotations

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from brilliant_chess.domain.expected_points import (
    expected_points_from_centipawns,
    expected_points_from_mate,
    expected_points_from_wdl,
    expected_points_loss,
    flip_expected_points,
)
from brilliant_chess.domain.gates import evaluate_gates
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.scoring import SCORE_MAX, brilliance_score, decide, quality_component
from tests.unit.test_gates import brilliant_inputs
from tests.unit.test_scoring import scoring_inputs

RULES = RuleSet()

centipawns = st.integers(min_value=-30_000, max_value=30_000)
mates = st.integers(min_value=-200, max_value=200).filter(lambda value: value != 0)
counts = st.integers(min_value=0, max_value=1000)
probabilities = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@given(centipawns)
def test_centipawn_mapping_stays_in_unit_interval(value):
    assert 0.0 <= expected_points_from_centipawns(value) <= 1.0


@given(mates)
def test_mate_mapping_stays_in_unit_interval(value):
    assert 0.0 <= expected_points_from_mate(value) <= 1.0


@given(counts, counts, counts)
def test_wdl_mapping_stays_in_unit_interval(wins, draws, losses):
    if wins + draws + losses == 0:
        return
    assert 0.0 <= expected_points_from_wdl((wins, draws, losses)) <= 1.0


@given(probabilities)
def test_flipping_twice_is_identity(value):
    assert abs(flip_expected_points(flip_expected_points(value)) - value) < 1e-12


@given(probabilities, probabilities)
def test_expected_points_loss_is_never_negative(best, candidate):
    if candidate > best:
        return
    assert expected_points_loss(best, candidate).value >= 0.0


@given(probabilities, probabilities)
def test_more_loss_never_increases_the_quality_component(first, second):
    low, high = sorted((first, second))
    assert quality_component(low, RULES) >= quality_component(high, RULES)


@given(probabilities, counts.map(lambda value: min(value, 50)))
def test_total_score_stays_between_zero_and_one_hundred(loss, alternatives):
    inputs = replace(
        scoring_inputs(), expected_points_loss=loss, equivalent_alternatives=alternatives
    )
    assert 0.0 <= brilliance_score(inputs, RULES) <= SCORE_MAX


@given(st.floats(min_value=0.951, max_value=1.0, allow_nan=False))
def test_already_winning_position_is_never_declared_brilliant(expected_points_before):
    gates = evaluate_gates(brilliant_inputs(expected_points_before=expected_points_before), RULES)
    decision = decide(gates, scoring_inputs(), RULES)
    assert decision.is_brilliant is False
    assert decision.selectable is False
