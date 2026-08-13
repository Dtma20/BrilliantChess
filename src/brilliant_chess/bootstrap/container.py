"""Montagem de dependencias. Sem estado global de motor ou configuracao."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from brilliant_chess.bootstrap.config import Settings, load_settings
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
    return Container(settings=settings, rules=settings.to_rule_set(), config_path=resolved)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
