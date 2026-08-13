from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.domain.gates import (
    GateInputs,
    all_gates_passed,
    evaluate_gates,
    failed_gates,
    gate_legal,
    gate_not_already_won,
    gate_not_bad_after,
    gate_quality,
    gate_sacrifice,
    gate_soundness,
    gate_stability,
    indeterminate_gates,
    is_near_threshold,
)
from brilliant_chess.domain.sacrifice import NO_SACRIFICE, SacrificeEvidence
from brilliant_chess.domain.values import GateId, GateStatus, PieceType, SacrificeKind

SOUND_SACRIFICE = SacrificeEvidence(
    detected=True,
    kind=SacrificeKind.DESTINATION_OFFER,
    offered_piece_square="h7",
    offered_piece_type=PieceType.ROOK,
    nominal_value=5.0,
    acceptance_moves=("g8h7",),
    material_trajectory=(0.0, -5.0, -5.0, 3.3),
    confidence=0.85,
)


def brilliant_inputs(**overrides) -> GateInputs:
    base = GateInputs(
        is_legal=True,
        expected_points_before=0.55,
        expected_points_after=0.71,
        expected_points_loss=0.002,
        confirmed_rank=1,
        sacrifice=SOUND_SACRIFICE,
        expected_points_loss_after_best_defense=0.004,
        expected_points_drift=0.005,
        pv_overlap_plies=4,
        sacrifice_persisted=True,
    )
    return replace(base, **overrides)


def test_illegal_move_fails_the_first_gate():
    assert gate_legal(is_legal=False).status is GateStatus.FAILED


def test_quality_gate_needs_both_loss_and_rank(rules):
    assert gate_quality(0.001, 1, rules.quality).passed
    assert not gate_quality(0.5, 1, rules.quality).passed
    assert not gate_quality(0.001, 7, rules.quality).passed


def test_sacrifice_gate_rejects_pawn_only_offer(rules):
    pawn_offer = replace(SOUND_SACRIFICE, offered_piece_type=PieceType.PAWN, nominal_value=1.0)
    assert not gate_sacrifice(pawn_offer, rules.sacrifice).passed


def test_sacrifice_gate_rejects_low_confidence(rules):
    assert not gate_sacrifice(replace(SOUND_SACRIFICE, confidence=0.2), rules.sacrifice).passed


def test_sacrifice_gate_rejects_absent_evidence(rules):
    assert not gate_sacrifice(NO_SACRIFICE, rules.sacrifice).passed


def test_soundness_is_indeterminate_without_best_defense(rules):
    assert gate_soundness(None, rules.quality).status is GateStatus.INDETERMINATE


def test_soundness_rejects_lines_that_need_an_opponent_error(rules):
    result = gate_soundness(0.001, rules.quality, depends_on_opponent_error=True)
    assert result.status is GateStatus.FAILED


def test_not_bad_after_accepts_forced_draw_when_configured(rules):
    assert not gate_not_bad_after(0.30, rules.resulting_position).passed
    assert gate_not_bad_after(0.30, rules.resulting_position, forced_draw_accepted=True).passed


def test_not_already_won_uses_the_prior_position(rules):
    assert gate_not_already_won(0.55, rules.prior_position).passed
    assert not gate_not_already_won(0.99, rules.prior_position).passed


def test_stability_without_budget_is_indeterminate_only_near_a_threshold(rules):
    near = gate_stability(None, None, None, rules.robustness, near_threshold=True)
    far = gate_stability(None, None, None, rules.robustness, near_threshold=False)
    assert near.status is GateStatus.INDETERMINATE
    assert far.status is GateStatus.PASSED


def test_stability_fails_on_drift_or_refuted_mechanism(rules):
    assert not gate_stability(0.2, 4, True, rules.robustness, near_threshold=False).passed
    assert not gate_stability(0.001, 4, False, rules.robustness, near_threshold=False).passed
    assert not gate_stability(0.001, 0, True, rules.robustness, near_threshold=False).passed


def test_full_evaluation_of_a_brilliant_candidate(rules):
    results = evaluate_gates(brilliant_inputs(), rules)
    assert all_gates_passed(results)
    assert failed_gates(results) == ()
    assert indeterminate_gates(results) == ()


def test_already_winning_position_is_rejected(rules):
    results = evaluate_gates(brilliant_inputs(expected_points_before=0.99), rules)
    assert not all_gates_passed(results)
    assert GateId.NOT_ALREADY_WON in failed_gates(results)


def test_bad_resulting_position_is_rejected(rules):
    results = evaluate_gates(
        brilliant_inputs(expected_points_after=0.20, expected_points_loss=0.40), rules
    )
    assert GateId.NOT_BAD_AFTER in failed_gates(results)


def test_near_threshold_detection_uses_configured_margin(rules):
    assert is_near_threshold(brilliant_inputs(expected_points_loss=0.014), rules)
    assert not is_near_threshold(brilliant_inputs(), rules)


@pytest.mark.parametrize("gate_id", list(GateId))
def test_every_gate_id_is_reported_exactly_once(rules, gate_id):
    results = evaluate_gates(brilliant_inputs(), rules)
    assert [result.gate_id for result in results].count(gate_id) == 1
