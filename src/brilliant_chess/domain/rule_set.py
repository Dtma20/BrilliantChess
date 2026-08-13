"""Limiares configuraveis das regras, como dataclasses puras.

Estes valores sao hipoteses de engenharia para iniciar calibracao. Nao sao
limiares oficiais do Chess.com. A camada ``bootstrap.config`` valida o YAML com
pydantic e converte para estes tipos; o dominio nunca importa pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from brilliant_chess.domain.errors import ConfigurationError
from brilliant_chess.domain.material import DEFAULT_MATERIAL_VALUES, MaterialValues
from brilliant_chess.domain.values import DEFAULT_RULE_SET_VERSION


@dataclass(frozen=True)
class QualityThresholds:
    max_expected_points_loss: float = 0.015
    require_top_n: int = 3


@dataclass(frozen=True)
class ResultingPositionThresholds:
    min_expected_points_after: float = 0.45


@dataclass(frozen=True)
class PriorPositionThresholds:
    max_expected_points_before: float = 0.95


@dataclass(frozen=True)
class SacrificeConfidenceWeights:
    """Pesos de 13.4. Cada evidencia conta uma unica vez."""

    legal_capture_available: float = 0.35
    material_deficit_in_acceptance: float = 0.20
    engine_considers_acceptance: float = 0.15
    tactical_mechanism_in_pv: float = 0.15
    persists_under_deeper_search: float = 0.15


@dataclass(frozen=True)
class SacrificeThresholds:
    min_nominal_value: float = 2.75
    min_confidence: float = 0.70
    acceptance_search_plies: int = 4
    compensation_horizon_plies: int = 10
    confidence_weights: SacrificeConfidenceWeights = field(
        default_factory=SacrificeConfidenceWeights
    )


@dataclass(frozen=True)
class RobustnessThresholds:
    max_ep_drift_on_deeper_search: float = 0.02
    min_pv_overlap_plies: int = 2
    #: Distancia de um limiar abaixo da qual a falta de estagio de estabilidade
    #: torna GATE_STABILITY_001 indeterminado em vez de aprovado.
    stability_threshold_margin: float = 0.01


@dataclass(frozen=True)
class ScoringWeights:
    quality: float = 30.0
    sacrifice: float = 35.0
    forcingness: float = 15.0
    uniqueness: float = 10.0
    robustness: float = 10.0

    @property
    def total(self) -> float:
        return self.quality + self.sacrifice + self.forcingness + self.uniqueness + self.robustness


@dataclass(frozen=True)
class SelectionThresholds:
    """Camada ``near_brilliant``: jogadas auditadas e objetivamente seguras."""

    safe_max_expected_points_loss: float = 0.03
    #: Margem de EP usada para contar alternativas equivalentes (unicidade).
    uniqueness_equivalence_margin: float = 0.02


@dataclass(frozen=True)
class RuleSet:
    id: str = DEFAULT_RULE_SET_VERSION
    rating_profile: str = "strict"
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    resulting_position: ResultingPositionThresholds = field(
        default_factory=ResultingPositionThresholds
    )
    prior_position: PriorPositionThresholds = field(default_factory=PriorPositionThresholds)
    sacrifice: SacrificeThresholds = field(default_factory=SacrificeThresholds)
    robustness: RobustnessThresholds = field(default_factory=RobustnessThresholds)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    selection: SelectionThresholds = field(default_factory=SelectionThresholds)
    material_values: MaterialValues = DEFAULT_MATERIAL_VALUES

    def __post_init__(self) -> None:
        if not self.id:
            raise ConfigurationError("RuleSet.id nao pode ser vazio")
        if self.quality.require_top_n < 1:
            raise ConfigurationError("require_top_n deve ser >= 1")
        if self.selection.safe_max_expected_points_loss < self.quality.max_expected_points_loss:
            raise ConfigurationError(
                "O limite de seguranca do seletor nao pode ser mais restritivo que "
                "o limite de qualidade dos portoes"
            )
