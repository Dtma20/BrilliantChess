"""Evidencia pura para o portao de nao obviedade em strict_v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NonObviousnessCondition(StrEnum):
    EP_IMPROVEMENT = "ep_improvement"
    RANK_IMPROVEMENT = "rank_improvement"
    EP_AND_RANK_IMPROVEMENT = "ep_and_rank_improvement"


@dataclass(frozen=True)
class NonObviousnessEvidence:
    shallow_rank: int | None = None
    deep_rank: int | None = None
    shallow_expected_points: float | None = None
    deep_expected_points: float | None = None
    expected_points_improvement: float | None = None
    shallow_nodes: int | None = None
    shallow_multipv: int | None = None
    condition: NonObviousnessCondition | None = None

    @property
    def passed(self) -> bool:
        return self.condition is not None

