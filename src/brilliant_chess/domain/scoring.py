"""Pontuacao de brilhantismo (0 a 100) e decisao final.

A pontuacao so e calculada depois dos portoes. Ela nunca transforma uma
candidata inelegivel em elegivel: candidatas reprovadas recebem apenas uma
pontuacao diagnostica marcada como nao selecionavel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from brilliant_chess.domain.errors import DomainError
from brilliant_chess.domain.gates import GateResult, all_gates_passed
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.sacrifice import SacrificeEvidence
from brilliant_chess.domain.values import SacrificeKind, WarningCode

SCORE_MIN: Final[float] = 0.0
SCORE_MAX: Final[float] = 100.0

#: Valor a partir do qual a magnitude do sacrificio satura. Evita favorecer
#: automaticamente a dama sobre a torre (secao 14.2 da especificacao).
SACRIFICE_VALUE_SATURATION: Final[float] = 5.0

#: Clareza tipica de cada tipo de sacrificio.
KIND_CLARITY: Final[dict[SacrificeKind, float]] = {
    SacrificeKind.DESTINATION_OFFER: 1.00,
    SacrificeKind.CLEARANCE_OR_DEFLECTION: 1.00,
    SacrificeKind.LEFT_HANGING: 0.95,
    SacrificeKind.EXCHANGE_SACRIFICE: 0.90,
    SacrificeKind.DECLINED_RECAPTURE: 0.90,
}

_UNKNOWN_EVIDENCE_SCORE: Final[float] = 0.5


@dataclass(frozen=True)
class ScoringInputs:
    expected_points_loss: float
    sacrifice: SacrificeEvidence
    net_material_conceded: float = 0.0
    replies_preserving_evaluation: int = 0
    total_legal_replies: int = 1
    forcing_moves_in_pv: int = 0
    pv_length: int = 0
    equivalent_alternatives: int = 0
    expected_points_drift: float | None = None
    pv_overlap_plies: int | None = None
    sacrifice_persisted: bool | None = None

    def __post_init__(self) -> None:
        if self.total_legal_replies < 1:
            raise DomainError("total_legal_replies deve ser >= 1")
        if self.replies_preserving_evaluation < 0:
            raise DomainError("replies_preserving_evaluation nao pode ser negativo")
        if self.equivalent_alternatives < 0:
            raise DomainError("equivalent_alternatives nao pode ser negativo")


@dataclass(frozen=True)
class ScoreBreakdown:
    quality: float
    sacrifice: float
    forcingness: float
    uniqueness: float
    robustness: float

    @property
    def total(self) -> float:
        return min(
            SCORE_MAX,
            max(
                SCORE_MIN,
                self.quality
                + self.sacrifice
                + self.forcingness
                + self.uniqueness
                + self.robustness,
            ),
        )


@dataclass(frozen=True)
class BrilliantDecision:
    is_brilliant: bool
    score: float
    gates: tuple[GateResult, ...]
    sacrifice: SacrificeEvidence
    breakdown: ScoreBreakdown
    rule_set_version: str
    selectable: bool = True
    warnings: tuple[WarningCode, ...] = ()
    reasons: tuple[str, ...] = field(default_factory=tuple)


def quality_component(expected_points_loss: float, rules: RuleSet) -> float:
    """Monotonicamente nao crescente em EP_loss. Perda zero recebe o maximo."""
    limit = rules.quality.max_expected_points_loss
    if limit <= 0.0:
        raise DomainError("max_expected_points_loss deve ser positivo")
    ratio = min(1.0, max(0.0, expected_points_loss / limit))
    return rules.scoring.quality * (1.0 - ratio)


def sacrifice_component(
    evidence: SacrificeEvidence,
    net_material_conceded: float,
    rules: RuleSet,
) -> float:
    if not evidence.detected:
        return 0.0
    value_ratio = min(1.0, evidence.nominal_value / SACRIFICE_VALUE_SATURATION)
    concession_ratio = min(1.0, max(0.0, net_material_conceded) / SACRIFICE_VALUE_SATURATION)
    clarity = KIND_CLARITY.get(evidence.kind, 0.9) if evidence.kind is not None else 0.9
    raw = 0.40 * value_ratio + 0.30 * concession_ratio + 0.30 * evidence.confidence
    return rules.scoring.sacrifice * raw * clarity


def forcingness_component(inputs: ScoringInputs, rules: RuleSet) -> float:
    preserving_ratio = min(1.0, inputs.replies_preserving_evaluation / inputs.total_legal_replies)
    reply_pressure = 1.0 - preserving_ratio
    pv_pressure = (
        min(1.0, inputs.forcing_moves_in_pv / inputs.pv_length) if inputs.pv_length > 0 else 0.0
    )
    return rules.scoring.forcingness * (0.60 * reply_pressure + 0.40 * pv_pressure)


def uniqueness_component(equivalent_alternatives: int, rules: RuleSet) -> float:
    """Quanto mais jogadas mantem praticamente o mesmo EP, menos unica e a ideia."""
    return rules.scoring.uniqueness * (1.0 / (1.0 + equivalent_alternatives))


def robustness_component(inputs: ScoringInputs, rules: RuleSet) -> float:
    max_drift = rules.robustness.max_ep_drift_on_deeper_search
    if inputs.expected_points_drift is None or max_drift <= 0.0:
        drift_score = _UNKNOWN_EVIDENCE_SCORE
    else:
        drift_score = 1.0 - min(1.0, abs(inputs.expected_points_drift) / max_drift)
    min_overlap = rules.robustness.min_pv_overlap_plies
    if inputs.pv_overlap_plies is None or min_overlap <= 0:
        overlap_score = _UNKNOWN_EVIDENCE_SCORE
    else:
        overlap_score = min(1.0, inputs.pv_overlap_plies / min_overlap)
    if inputs.sacrifice_persisted is None:
        persistence_score = _UNKNOWN_EVIDENCE_SCORE
    else:
        persistence_score = 1.0 if inputs.sacrifice_persisted else 0.0
    raw = 0.40 * drift_score + 0.30 * overlap_score + 0.30 * persistence_score
    return rules.scoring.robustness * raw


def score_breakdown(inputs: ScoringInputs, rules: RuleSet) -> ScoreBreakdown:
    return ScoreBreakdown(
        quality=quality_component(inputs.expected_points_loss, rules),
        sacrifice=sacrifice_component(inputs.sacrifice, inputs.net_material_conceded, rules),
        forcingness=forcingness_component(inputs, rules),
        uniqueness=uniqueness_component(inputs.equivalent_alternatives, rules),
        robustness=robustness_component(inputs, rules),
    )


def brilliance_score(inputs: ScoringInputs, rules: RuleSet) -> float:
    return score_breakdown(inputs, rules).total


def decide(
    gates: tuple[GateResult, ...],
    inputs: ScoringInputs,
    rules: RuleSet,
    warnings: tuple[WarningCode, ...] = (),
) -> BrilliantDecision:
    """Combina portoes e pontuacao sem deixar o estilo sobrepor a elegibilidade."""
    eligible = all_gates_passed(gates)
    breakdown = score_breakdown(inputs, rules)
    return BrilliantDecision(
        is_brilliant=eligible,
        score=breakdown.total,
        gates=gates,
        sacrifice=inputs.sacrifice,
        breakdown=breakdown,
        rule_set_version=rules.id,
        selectable=eligible,
        warnings=warnings,
        reasons=tuple(gate.gate_id.value for gate in gates if gate.passed),
    )
