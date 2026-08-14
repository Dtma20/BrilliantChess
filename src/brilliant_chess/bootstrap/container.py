"""Montagem de dependencias. Sem estado global de motor ou configuracao."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from brilliant_chess.bootstrap.config import Settings, load_settings
from brilliant_chess.domain.errors import ConfigurationError
from brilliant_chess.domain.models import AnalysisBudget
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.values import AnalysisStage


@dataclass(frozen=True)
class Container:
    """Objetos de longa duracao de uma execucao da CLI.

    O motor nao entra aqui: ele e criado por caso de uso, com ciclo de vida
    explicito, para garantir encerramento mesmo com excecao (Entrega 2).
    """

    settings: Settings
    rules: RuleSet
    config_path: Path
    v1_rules: RuleSet | None = None
    v2_rules: RuleSet | None = None

    def rule_set_for(self, policy: str) -> RuleSet:
        value = getattr(policy, "value", policy)
        if value == "strict_v1":
            return self.v1_rules or self.rules
        if value == "strict_v2":
            return self.v2_rules or self.rules
        raise ConfigurationError(f"A politica {value!r} nao possui RuleSet")

    def budget_for(self, stage: AnalysisStage) -> AnalysisBudget:
        engine = self.settings.engine
        if stage is AnalysisStage.DISCOVERY:
            return AnalysisBudget(nodes=engine.discovery.nodes)
        if stage is AnalysisStage.CONFIRMATION:
            return AnalysisBudget(nodes=engine.confirmation.nodes_per_candidate)
        return AnalysisBudget(nodes=engine.stability.nodes_per_candidate)

    @property
    def database_path(self) -> Path:
        return Path(self.settings.storage.database_path)


def build_container(config_path: Path | None = None) -> Container:
    resolved = config_path or Path("config/strict_v1.yaml")
    settings = load_settings(resolved)
    _configure_logging(settings.logging.level)
    configured_rules = settings.to_rule_set()
    v1_rules = (
        configured_rules
        if configured_rules.id == "strict_v1"
        else load_settings(_shipped_config("strict_v1.yaml")).to_rule_set()
    )
    v2_path = (
        resolved if resolved.name == "strict_v2.yaml" else resolved.with_name("strict_v2.yaml")
    )
    if not v2_path.exists():
        v2_path = _shipped_config("strict_v2.yaml")
    v2_rules = (
        configured_rules
        if configured_rules.id == "strict_v2"
        else load_settings(v2_path).to_rule_set()
    )
    return Container(
        settings=settings,
        rules=configured_rules,
        config_path=resolved,
        v1_rules=v1_rules,
        v2_rules=v2_rules,
    )


def _shipped_config(name: str) -> Path:
    return Path(__file__).resolve().parents[3] / "config" / name


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
