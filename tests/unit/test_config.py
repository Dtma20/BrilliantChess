from __future__ import annotations

from pathlib import Path

import pytest

from brilliant_chess.bootstrap.config import (
    ENGINE_PATH_ENV_VAR,
    LEGACY_ENGINE_PATH_ENV_VAR,
    Settings,
    load_settings,
)
from brilliant_chess.bootstrap.container import build_container
from brilliant_chess.domain.errors import ConfigurationError
from brilliant_chess.domain.values import AnalysisStage
from brilliant_chess.interfaces.web.schemas import NewMatchIn

STRICT_CONFIG = Path("config/strict_v1.yaml")
STRICT_V2_CONFIG = Path("config/strict_v2.yaml")
DEV_CONFIG = Path("config/development.yaml")


def test_shipped_configs_load_and_convert_to_rule_sets():
    for path in (STRICT_CONFIG, DEV_CONFIG):
        settings = load_settings(path)
        rules = settings.to_rule_set()
        assert rules.id == "strict_v1"
        assert rules.quality.max_expected_points_loss == pytest.approx(0.015)
        assert rules.scoring.total == pytest.approx(100.0)


def test_shipped_v2_config_loads_separately():
    settings = load_settings(STRICT_V2_CONFIG)

    assert settings.to_rule_set().id == "strict_v2"
    assert settings.to_rule_set().non_obviousness.shallow_nodes == 5_000
    assert settings.to_rule_set().sacrifice.exchange_search_plies == 8


def test_container_resolves_both_historical_and_v2_rules():
    container = build_container(STRICT_CONFIG)

    assert container.rule_set_for("strict_v1").id == "strict_v1"
    assert container.rule_set_for("strict_v2").id == "strict_v2"


def test_missing_file_is_a_configuration_error(tmp_path):
    with pytest.raises(ConfigurationError):
        load_settings(tmp_path / "ausente.yaml")


def test_unknown_key_is_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("rules:\n  chave_desconhecida: 1\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_out_of_range_threshold_is_rejected(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("rules:\n  quality:\n    max_expected_points_loss: 2.0\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_invalid_yaml_is_reported_as_configuration_error(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("rules: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_engine_path_precedence(monkeypatch):
    settings = Settings.model_validate({"engine": {"binary_path": "C:/from/config.exe"}})
    monkeypatch.delenv(ENGINE_PATH_ENV_VAR, raising=False)
    monkeypatch.delenv(LEGACY_ENGINE_PATH_ENV_VAR, raising=False)
    assert settings.resolved_engine_path() == "C:/from/config.exe"

    monkeypatch.setenv(LEGACY_ENGINE_PATH_ENV_VAR, "C:/legacy.exe")
    assert settings.resolved_engine_path() == "C:/legacy.exe"

    monkeypatch.setenv(ENGINE_PATH_ENV_VAR, "C:/project.exe")
    assert settings.resolved_engine_path() == "C:/project.exe"


def test_container_maps_each_stage_to_its_node_budget():
    container = build_container(STRICT_CONFIG)
    assert container.budget_for(AnalysisStage.DISCOVERY).nodes == 400_000
    assert container.budget_for(AnalysisStage.CONFIRMATION).nodes == 1_500_000
    assert container.budget_for(AnalysisStage.STABILITY).nodes == 4_000_000
    assert all(container.budget_for(stage).is_deterministic for stage in AnalysisStage)


def test_lab_config_uses_fixed_node_budgets():
    lab = Settings().web.lab

    assert lab.max_fullmoves == 100
    assert lab.strict_budget().discovery.nodes == 80_000
    assert lab.strict_budget().confirmation.nodes == 200_000
    assert lab.strict_budget().best_defense.nodes == 200_000
    assert lab.strict_budget().stability is not None
    assert lab.strict_budget().stability.nodes == 400_000
    assert lab.strict_budget().max_candidates == 6


def test_omitted_api_match_policy_remains_strict_v1():
    assert NewMatchIn().white.policy.value == "strict_v1"
