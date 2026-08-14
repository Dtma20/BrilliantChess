from __future__ import annotations

import pytest

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.exchange import ExchangeDisposition, ExchangeEvidence
from brilliant_chess.domain.sacrifice import (
    NO_SACRIFICE,
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.values import PieceType, ReasonCode, SacrificeKind


@pytest.fixture
def rules_v2() -> RuleSet:
    return RuleSet(id="strict_v2")


def test_no_evidence_gives_zero_confidence(rules):
    assert sacrifice_confidence(SacrificeSignals(), rules.sacrifice.confidence_weights) == 0.0


def test_confidence_sums_configured_weights(rules):
    signals = SacrificeSignals(
        legal_capture_available=True,
        material_deficit_in_acceptance=True,
        engine_considers_acceptance=True,
    )
    assert sacrifice_confidence(signals, rules.sacrifice.confidence_weights) == pytest.approx(0.70)


def test_confidence_never_exceeds_one(rules):
    signals = SacrificeSignals(
        legal_capture_available=True,
        material_deficit_in_acceptance=True,
        engine_considers_acceptance=True,
        tactical_mechanism_in_pv=True,
        persists_under_deeper_search=True,
    )
    assert sacrifice_confidence(signals, rules.sacrifice.confidence_weights) == 1.0


def test_unknown_persistence_does_not_count_as_evidence(rules):
    weights = rules.sacrifice.confidence_weights
    unknown = SacrificeSignals(legal_capture_available=True, persists_under_deeper_search=None)
    known = SacrificeSignals(legal_capture_available=True, persists_under_deeper_search=True)
    assert sacrifice_confidence(unknown, weights) < sacrifice_confidence(known, weights)


def test_reasons_reflect_only_observed_signals():
    reasons = reasons_for(
        SacrificeSignals(legal_capture_available=True, tactical_mechanism_in_pv=True)
    )
    assert reasons == (
        ReasonCode.LEGAL_CAPTURE_OF_OFFERED_PIECE,
        ReasonCode.TACTICAL_MECHANISM_IN_PV,
    )


def test_detected_evidence_requires_a_kind():
    with pytest.raises(DomainError):
        SacrificeEvidence(detected=True, kind=None)


def test_confidence_outside_range_is_rejected():
    with pytest.raises(DomainError):
        SacrificeEvidence(detected=False, confidence=1.5)


def test_offers_piece_is_false_for_pawn_and_none():
    assert NO_SACRIFICE.offers_piece is False
    pawn = SacrificeEvidence(
        detected=True,
        kind=SacrificeKind.DESTINATION_OFFER,
        offered_piece_type=PieceType.PAWN,
        nominal_value=1.0,
    )
    assert pawn.offers_piece is False


def test_v2_exchange_evidence_is_kept_on_sacrifice_object():
    exchange = ExchangeEvidence(
        disposition=ExchangeDisposition.TEMPORARY_OFFER,
        material_before=0.0,
        material_immediately_after=-3.0,
        material_after_best_acceptance=-1.0,
        net_material_concession=2.0,
    )
    evidence = SacrificeEvidence(detected=False, exchange=exchange)
    assert evidence.exchange is exchange
