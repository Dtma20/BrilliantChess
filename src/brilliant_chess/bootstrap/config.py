"""Configuracao validada com pydantic e traduzida para tipos puros do dominio.

O dominio nao importa pydantic. Este modulo e a unica fronteira entre YAML e
``RuleSet``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from brilliant_chess.domain.errors import ConfigurationError
from brilliant_chess.domain.material import MaterialValues
from brilliant_chess.domain.rule_set import (
    PriorPositionThresholds,
    QualityThresholds,
    ResultingPositionThresholds,
    RobustnessThresholds,
    RuleSet,
    SacrificeConfidenceWeights,
    SacrificeThresholds,
    ScoringWeights,
    SelectionThresholds,
)

ENGINE_PATH_ENV_VAR = "BRILLIANT_CHESS_STOCKFISH"
LEGACY_ENGINE_PATH_ENV_VAR = "STOCKFISH_PATH"
DEFAULT_CONFIG_PATH = Path("config/strict_v1.yaml")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QualityModel(_Strict):
    max_expected_points_loss: float = Field(default=0.015, gt=0.0, le=1.0)
    require_top_n: int = Field(default=3, ge=1)


class ResultingPositionModel(_Strict):
    min_expected_points_after: float = Field(default=0.45, ge=0.0, le=1.0)


class PriorPositionModel(_Strict):
    max_expected_points_before: float = Field(default=0.95, ge=0.0, le=1.0)


class ConfidenceWeightsModel(_Strict):
    legal_capture_available: float = Field(default=0.35, ge=0.0, le=1.0)
    material_deficit_in_acceptance: float = Field(default=0.20, ge=0.0, le=1.0)
    engine_considers_acceptance: float = Field(default=0.15, ge=0.0, le=1.0)
    tactical_mechanism_in_pv: float = Field(default=0.15, ge=0.0, le=1.0)
    persists_under_deeper_search: float = Field(default=0.15, ge=0.0, le=1.0)


class SacrificeModel(_Strict):
    min_nominal_value: float = Field(default=2.75, gt=0.0)
    min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    acceptance_search_plies: int = Field(default=4, ge=1)
    compensation_horizon_plies: int = Field(default=10, ge=1)
    confidence_weights: ConfidenceWeightsModel = ConfidenceWeightsModel()


class RobustnessModel(_Strict):
    max_ep_drift_on_deeper_search: float = Field(default=0.02, ge=0.0, le=1.0)
    min_pv_overlap_plies: int = Field(default=2, ge=0)
    stability_threshold_margin: float = Field(default=0.01, ge=0.0, le=1.0)


class ScoringModel(_Strict):
    quality_weight: float = Field(default=30.0, ge=0.0)
    sacrifice_weight: float = Field(default=35.0, ge=0.0)
    forcingness_weight: float = Field(default=15.0, ge=0.0)
    uniqueness_weight: float = Field(default=10.0, ge=0.0)
    robustness_weight: float = Field(default=10.0, ge=0.0)


class SelectionModel(_Strict):
    safe_max_expected_points_loss: float = Field(default=0.03, ge=0.0, le=1.0)
    uniqueness_equivalence_margin: float = Field(default=0.02, ge=0.0, le=1.0)


class MaterialValuesModel(_Strict):
    pawn: float = Field(default=1.0, gt=0.0)
    knight: float = Field(default=3.2, gt=0.0)
    bishop: float = Field(default=3.3, gt=0.0)
    rook: float = Field(default=5.0, gt=0.0)
    queen: float = Field(default=9.0, gt=0.0)


class RulesModel(_Strict):
    id: str = "strict_v1"
    rating_profile: str = "strict"
    quality: QualityModel = QualityModel()
    resulting_position: ResultingPositionModel = ResultingPositionModel()
    prior_position: PriorPositionModel = PriorPositionModel()
    sacrifice: SacrificeModel = SacrificeModel()
    robustness: RobustnessModel = RobustnessModel()
    scoring: ScoringModel = ScoringModel()
    selection: SelectionModel = SelectionModel()
    material_values: MaterialValuesModel = MaterialValuesModel()


class DiscoveryModel(_Strict):
    multipv: int = Field(default=12, ge=1)
    nodes: int = Field(default=400_000, gt=0)


class ConfirmationModel(_Strict):
    candidates: int = Field(default=6, ge=1)
    nodes_per_candidate: int = Field(default=1_500_000, gt=0)


class StabilityModel(_Strict):
    enabled: bool = True
    nodes_per_candidate: int = Field(default=4_000_000, gt=0)


class EngineModel(_Strict):
    #: Caminho do executavel; ``null`` delega a deteccao por PATH/variavel.
    binary_path: str | None = None
    threads: int = Field(default=6, ge=1)
    hash_mb: int = Field(default=1024, ge=16)
    workers: int = Field(default=1, ge=1)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    discovery: DiscoveryModel = DiscoveryModel()
    confirmation: ConfirmationModel = ConfirmationModel()
    stability: StabilityModel = StabilityModel()


class WebModel(_Strict):
    """Interface web local. O host padrao e loopback por decisao de fair play."""

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    analysis_multipv: int = Field(default=6, ge=1, le=32)
    analysis_discovery_nodes: int = Field(default=300_000, gt=0)
    analysis_confirmation_nodes: int = Field(default=700_000, gt=0)
    max_arrows: int = Field(default=3, ge=1, le=8)


class StorageModel(_Strict):
    database_path: str = "data/brilliant_chess.sqlite3"


class LoggingModel(_Strict):
    level: str = "INFO"


class Settings(_Strict):
    rules: RulesModel = RulesModel()
    engine: EngineModel = EngineModel()
    web: WebModel = WebModel()
    storage: StorageModel = StorageModel()
    logging: LoggingModel = LoggingModel()

    def to_rule_set(self) -> RuleSet:
        return _rule_set_from(self.rules)

    def resolved_engine_path(self) -> str | None:
        """Precedencia: variavel de ambiente do projeto, legado, configuracao."""
        return (
            os.environ.get(ENGINE_PATH_ENV_VAR)
            or os.environ.get(LEGACY_ENGINE_PATH_ENV_VAR)
            or self.engine.binary_path
        )


def load_settings(path: Path | None = None) -> Settings:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise ConfigurationError(f"Arquivo de configuracao nao encontrado: {config_path}")
    try:
        raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"YAML invalido em {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Configuracao deve ser um mapeamento: {config_path}")
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"Configuracao invalida em {config_path}:\n{exc}") from exc


def _rule_set_from(rules: RulesModel) -> RuleSet:
    weights = rules.sacrifice.confidence_weights
    return RuleSet(
        id=rules.id,
        rating_profile=rules.rating_profile,
        quality=QualityThresholds(
            max_expected_points_loss=rules.quality.max_expected_points_loss,
            require_top_n=rules.quality.require_top_n,
        ),
        resulting_position=ResultingPositionThresholds(
            min_expected_points_after=rules.resulting_position.min_expected_points_after,
        ),
        prior_position=PriorPositionThresholds(
            max_expected_points_before=rules.prior_position.max_expected_points_before,
        ),
        sacrifice=SacrificeThresholds(
            min_nominal_value=rules.sacrifice.min_nominal_value,
            min_confidence=rules.sacrifice.min_confidence,
            acceptance_search_plies=rules.sacrifice.acceptance_search_plies,
            compensation_horizon_plies=rules.sacrifice.compensation_horizon_plies,
            confidence_weights=SacrificeConfidenceWeights(
                legal_capture_available=weights.legal_capture_available,
                material_deficit_in_acceptance=weights.material_deficit_in_acceptance,
                engine_considers_acceptance=weights.engine_considers_acceptance,
                tactical_mechanism_in_pv=weights.tactical_mechanism_in_pv,
                persists_under_deeper_search=weights.persists_under_deeper_search,
            ),
        ),
        robustness=RobustnessThresholds(
            max_ep_drift_on_deeper_search=rules.robustness.max_ep_drift_on_deeper_search,
            min_pv_overlap_plies=rules.robustness.min_pv_overlap_plies,
            stability_threshold_margin=rules.robustness.stability_threshold_margin,
        ),
        scoring=ScoringWeights(
            quality=rules.scoring.quality_weight,
            sacrifice=rules.scoring.sacrifice_weight,
            forcingness=rules.scoring.forcingness_weight,
            uniqueness=rules.scoring.uniqueness_weight,
            robustness=rules.scoring.robustness_weight,
        ),
        selection=SelectionThresholds(
            safe_max_expected_points_loss=rules.selection.safe_max_expected_points_loss,
            uniqueness_equivalence_margin=rules.selection.uniqueness_equivalence_margin,
        ),
        material_values=MaterialValues(
            pawn=rules.material_values.pawn,
            knight=rules.material_values.knight,
            bishop=rules.material_values.bishop,
            rook=rules.material_values.rook,
            queen=rules.material_values.queen,
        ),
    )
