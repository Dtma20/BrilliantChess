from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.exchange import ExchangeDisposition, ExchangeEvidence
from brilliant_chess.domain.gates import GateResult, evaluate_gates
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.scoring import (
    SCORE_MAX,
    ScoringInputs,
    brilliance_score,
    decide,
    quality_component,
    sacrifice_component,
    score_breakdown,
    uniqueness_component,
)
from brilliant_chess.domain.sacrifice import SacrificeEvidence
from brilliant_chess.domain.values import GateId, GateStatus, PieceType
from tests.unit.test_gates import SOUND_SACRIFICE, brilliant_inputs


@pytest.fixture
def rules_v2() -> RuleSet:
    return RuleSet(id="strict_v2")


def scoring_inputs(**overrides) -> ScoringInputs:
    base = ScoringInputs(
        expected_points_loss=0.002,
        sacrifice=SOUND_SACRIFICE,
        net_material_conceded=5.0,
        replies_preserving_evaluation=1,
        total_legal_replies=30,
        forcing_moves_in_pv=4,
        pv_length=6,
        equivalent_alternatives=0,
        expected_points_drift=0.001,
        pv_overlap_plies=4,
        sacrifice_persisted=True,
    )
    return replace(base, **overrides)


def test_quality_component_is_monotonically_non_increasing(rules):
    losses = [0.0, 0.005, 0.010, 0.015, 0.100]
    scores = [quality_component(loss, rules) for loss in losses]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(rules.scoring.quality)
    assert scores[-1] == pytest.approx(0.0)


def test_score_stays_inside_zero_and_one_hundred(rules):
    assert 0.0 <= brilliance_score(scoring_inputs(), rules) <= SCORE_MAX
    weak = scoring_inputs(
        expected_points_loss=1.0,
        sacrifice=replace(SOUND_SACRIFICE, detected=False),
        net_material_conceded=0.0,
        replies_preserving_evaluation=30,
        forcing_moves_in_pv=0,
        equivalent_alternatives=9,
        expected_points_drift=1.0,
        pv_overlap_plies=0,
        sacrifice_persisted=False,
    )
    # Sobra apenas o componente de unicidade residual; nada de qualidade ou sacrificio.
    assert brilliance_score(weak, rules) == pytest.approx(rules.scoring.uniqueness / 10.0)


def test_queen_offer_does_not_automatically_beat_rook_offer(rules):
    rook = SOUND_SACRIFICE
    queen = replace(rook, offered_piece_type=PieceType.QUEEN, nominal_value=9.0)
    assert sacrifice_component(queen, 5.0, rules) == pytest.approx(
        sacrifice_component(rook, 5.0, rules)
    )


def test_undetected_sacrifice_scores_zero_in_that_component(rules):
    undetected = replace(SOUND_SACRIFICE, detected=False)
    assert sacrifice_component(undetected, 5.0, rules) == 0.0


def test_v2_sacrifice_component_prefers_exchange_net_concession(rules_v2):
    evidence = replace(
        SOUND_SACRIFICE,
        exchange=ExchangeEvidence(
            disposition=ExchangeDisposition.EXCHANGE_SACRIFICE,
            material_before=0.0,
            material_immediately_after=-3.0,
            material_after_best_acceptance=-1.5,
            net_material_concession=1.5,
        ),
    )
    assert sacrifice_component(evidence, 5.0, rules_v2) == pytest.approx(
        sacrifice_component(evidence, 1.5, rules_v2)
    )


def test_uniqueness_decreases_with_equivalent_alternatives(rules):
    values = [uniqueness_component(n, rules) for n in (0, 1, 3, 10)]
    assert values == sorted(values, reverse=True)


def test_components_respect_their_weight_caps(rules):
    breakdown = score_breakdown(scoring_inputs(), rules)
    assert breakdown.quality <= rules.scoring.quality
    assert breakdown.sacrifice <= rules.scoring.sacrifice
    assert breakdown.forcingness <= rules.scoring.forcingness
    assert breakdown.uniqueness <= rules.scoring.uniqueness
    assert breakdown.robustness <= rules.scoring.robustness


def test_scoring_inputs_validate_counts():
    with pytest.raises(DomainError):
        ScoringInputs(expected_points_loss=0.0, sacrifice=SOUND_SACRIFICE, total_legal_replies=0)


def test_decision_marks_ineligible_candidates_as_non_selectable(rules):
    gates = evaluate_gates(brilliant_inputs(expected_points_before=0.99), rules)
    decision = decide(gates, scoring_inputs(), rules)
    assert decision.is_brilliant is False
    assert decision.selectable is False
    assert decision.score > 0.0


def test_decision_of_a_brilliant_candidate_is_selectable(rules):
    gates = evaluate_gates(brilliant_inputs(), rules)
    decision = decide(gates, scoring_inputs(), rules)
    assert decision.is_brilliant is True
    assert decision.selectable is True
    assert decision.rule_set_version == rules.id
    assert len(decision.gates) == len(gates)


def test_v2_score_does_not_override_failed_mandatory_gate(rules_v2):
    inputs = ScoringInputs(
        expected_points_loss=0.0,
        sacrifice=SacrificeEvidence(detected=False),
    )
    decision = decide(
        (GateResult(GateId.NON_OBVIOUS, GateStatus.FAILED, False, True, "obvious"),),
        inputs,
        rules_v2,
    )
    assert decision.selectable is False
    assert decision.is_brilliant is False
