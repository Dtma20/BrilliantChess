from __future__ import annotations

import pytest

from brilliant_chess.bootstrap.config import Settings
from brilliant_chess.domain.opening import (
    OpeningConfig,
    OpeningIdentity,
    OpeningLine,
    OpeningMode,
    OpeningPhaseState,
)


def test_opening_modes_and_default_are_typed():
    settings = Settings()
    assert settings.web.lab.opening.default_mode is OpeningMode.EXPLORATORY
    exp_cfg = settings.web.lab.opening.for_mode(OpeningMode.EXPLORATORY)
    assert exp_cfg.multipv == 6
    assert exp_cfg.max_ep_loss == pytest.approx(0.08)


def test_opening_line_requires_nonempty_legal_sequence_shape():
    line = OpeningLine(
        line_id="e4-italian",
        family="e4",
        eco="C50",
        name="Italian Game",
        variation="Giuoco Piano",
        moves_uci=("e2e4", "e7e5"),
        weight=1.0,
    )
    assert line.moves_uci[0] == "e2e4"
    assert line.line_id == "e4-italian"


def test_chaotic_mode_is_experimental():
    assert Settings().web.lab.opening.for_mode(OpeningMode.CHAOTIC).experimental is True


def test_opening_modes_are_all_serializable():
    assert {mode.value for mode in OpeningMode} == {
        "off",
        "controlled",
        "exploratory",
        "chaotic",
    }


def test_opening_config_with_seed():
    config = OpeningConfig(mode=OpeningMode.EXPLORATORY)
    assert config.seed is None
    seeded = config.with_seed(42)
    assert seeded.seed == 42
    assert seeded.mode is OpeningMode.EXPLORATORY


def test_opening_phase_state_and_identity():
    identity = OpeningIdentity(
        line_id="e4-italian",
        family="e4",
        eco="C50",
        name="Italian Game",
    )
    phase = OpeningPhaseState(
        active=True,
        mode=OpeningMode.EXPLORATORY,
        seed=123,
        planned_exit_ply=10,
        completed_opening_plies=2,
        current_phase="suite",
        selected_identity=identity,
    )
    assert phase.active is True
    assert phase.exit_reason is None
    assert phase.selected_identity.line_id == "e4-italian"
