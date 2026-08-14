from __future__ import annotations

import pytest

from brilliant_chess.domain.gates import gate_non_obviousness
from brilliant_chess.domain.non_obviousness import (
    NonObviousnessCondition,
    NonObviousnessEvidence,
)
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.values import GateStatus


@pytest.fixture
def thresholds():
    return RuleSet(id="strict_v2").non_obviousness


def evidence(**overrides) -> NonObviousnessEvidence:
    values = {
        "shallow_rank": 5,
        "deep_rank": 2,
        "shallow_expected_points": 0.50,
        "deep_expected_points": 0.55,
        "expected_points_improvement": 0.05,
        "shallow_nodes": 5_000,
        "shallow_multipv": 5,
        "condition": NonObviousnessCondition.EP_IMPROVEMENT,
    }
    values.update(overrides)
    return NonObviousnessEvidence(**values)


def test_ep_improvement_can_pass_without_rank_improvement(thresholds):
    result = gate_non_obviousness(
        evidence(
            shallow_rank=1,
            deep_rank=1,
            expected_points_improvement=0.04,
        ),
        thresholds,
    )

    assert result.status is GateStatus.PASSED


def test_rank_improvement_can_pass_without_ep_improvement(thresholds):
    result = gate_non_obviousness(
        evidence(
            shallow_rank=5,
            deep_rank=2,
            expected_points_improvement=0.01,
            condition=NonObviousnessCondition.RANK_IMPROVEMENT,
        ),
        thresholds,
    )

    assert result.status is GateStatus.PASSED


def test_shallow_top_two_escape_can_pass_without_ep_or_rank_gain(thresholds):
    result = gate_non_obviousness(
        evidence(
            shallow_rank=3,
            deep_rank=3,
            expected_points_improvement=0.01,
            condition=NonObviousnessCondition.SHALLOW_OBVIOUSNESS,
        ),
        thresholds,
    )

    assert result.status is GateStatus.PASSED


def test_missing_shallow_or_deep_evidence_fails_conservatively(thresholds):
    result = gate_non_obviousness(
        evidence(shallow_expected_points=None, deep_rank=2),
        thresholds,
    )

    assert result.status is GateStatus.FAILED


def test_ep_improvement_accepts_missing_shallow_rank_from_root_search(thresholds):
    result = gate_non_obviousness(
        evidence(shallow_rank=None, condition=NonObviousnessCondition.EP_IMPROVEMENT),
        thresholds,
    )

    assert result.status is GateStatus.PASSED
