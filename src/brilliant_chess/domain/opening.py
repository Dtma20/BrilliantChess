"""Modelos puros do dominio para exploracao deterministica de aberturas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from brilliant_chess.domain.models import AnalysisBudget


class OpeningMode(StrEnum):
    OFF = "off"
    CONTROLLED = "controlled"
    EXPLORATORY = "exploratory"
    CHAOTIC = "chaotic"


class OpeningPhase(StrEnum):
    SUITE = "suite"
    MULTIPV_SAMPLING = "multipv_sampling"
    ENDED = "ended"


class OpeningExitReason(StrEnum):
    PLANNED_EXIT = "planned_exit"
    TERMINAL_POSITION = "terminal_position"
    NO_COMPATIBLE_LINE = "no_compatible_line"
    NO_ACCEPTABLE_CANDIDATE = "no_acceptable_candidate"
    ENGINE_ERROR = "engine_error"
    DISABLED = "disabled"
    LINE_EXHAUSTED = "line_exhausted"


@dataclass(frozen=True)
class OpeningLine:
    line_id: str
    family: str
    eco: str
    name: str
    moves_uci: tuple[str, ...]
    variation: str | None = None
    weight: float = 1.0


@dataclass(frozen=True)
class OpeningIdentity:
    line_id: str
    family: str
    eco: str
    name: str
    variation: str | None = None


@dataclass(frozen=True)
class OpeningConfig:
    mode: OpeningMode
    seed: int | None = None
    line_id: str | None = None
    min_fullmove: int = 4
    max_fullmove: int = 10
    multipv: int = 6
    max_ep_loss: float = 0.08
    temperature: float = 0.04
    extra_plies: int = 3
    budget_nodes: int = 5000
    experimental: bool = False

    def with_seed(self, seed: int | None) -> OpeningConfig:
        return replace(self, seed=seed)


@dataclass(frozen=True)
class OpeningPhaseState:
    active: bool
    mode: OpeningMode
    seed: int
    planned_exit_ply: int
    completed_opening_plies: int = 0
    current_phase: str = "suite"
    exit_reason: OpeningExitReason | None = None
    selected_identity: OpeningIdentity | None = None


@dataclass(frozen=True)
class OpeningMoveAudit:
    opening_mode: OpeningMode
    seed: int
    eco: str
    name: str
    variation: str | None
    source: str
    opening_ply: int
    planned_exit_ply: int
    candidate_rank: int | None = None
    candidate_ep_loss: float | None = None
    sampling_weight: float | None = None
    candidates_considered: tuple[str, ...] = ()
    quality_cutoff: float | None = None
    search_budget: AnalysisBudget | None = None
    sampling_mode: str | None = None
    experimental: bool = False
