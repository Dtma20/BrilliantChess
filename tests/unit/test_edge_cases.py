"""Casos de borda que fecham os ramos de validacao do dominio."""

from __future__ import annotations

from dataclasses import replace

import pytest

from brilliant_chess.application import play_game
from brilliant_chess.bootstrap.config import Settings
from brilliant_chess.domain.errors import (
    ConfigurationError,
    DomainError,
    EngineNotFoundError,
    InvalidEvaluationError,
    InvalidFenError,
)
from brilliant_chess.domain.models import AnalysisBudget, NormalizedEvaluation, Position
from brilliant_chess.domain.rule_set import QualityThresholds, RuleSet, SelectionThresholds
from brilliant_chess.domain.sacrifice import (
    SacrificeEvidence,
    SacrificeSignals,
    reasons_for,
    sacrifice_confidence,
)
from brilliant_chess.domain.scoring import (
    ScoringInputs,
    quality_component,
    robustness_component,
    sacrifice_component,
)
from brilliant_chess.domain.strength import EngineStrength, strength_by_key
from brilliant_chess.domain.values import Color, PieceType, ReasonCode, SacrificeKind
from brilliant_chess.interfaces.cli.app import main
from brilliant_chess.interfaces.web.engine_session import EngineSession
from brilliant_chess.interfaces.web.game_store import GameStore
from tests.conftest import STARTPOS
from tests.unit.test_gates import SOUND_SACRIFICE
from tests.unit.test_scoring import scoring_inputs


def test_position_constructed_directly_validates_every_field():
    with pytest.raises(InvalidFenError):
        Position(fen="8/8 w", side_to_move=Color.WHITE)
    with pytest.raises(InvalidFenError):
        Position(fen="8/8/8/8/8/8/8/8 x - - 0 1", side_to_move=Color.WHITE)


def test_budget_rejects_non_positive_limits():
    with pytest.raises(DomainError):
        AnalysisBudget(nodes=0)
    with pytest.raises(DomainError):
        AnalysisBudget(depth=-1)
    with pytest.raises(DomainError):
        AnalysisBudget(time_seconds=0.0)


def test_evaluation_without_any_score_is_rejected_on_direct_construction():
    with pytest.raises(InvalidEvaluationError):
        NormalizedEvaluation(mover=Color.WHITE, centipawns=None, mate_in=None, expected_points=0.5)


def test_rule_set_validates_its_own_consistency():
    with pytest.raises(ConfigurationError):
        RuleSet(id="")
    with pytest.raises(ConfigurationError):
        RuleSet(quality=QualityThresholds(require_top_n=0))
    with pytest.raises(ConfigurationError):
        RuleSet(
            quality=QualityThresholds(max_expected_points_loss=0.05),
            selection=SelectionThresholds(safe_max_expected_points_loss=0.01),
        )


def test_negative_nominal_value_is_rejected():
    with pytest.raises(DomainError):
        SacrificeEvidence(detected=False, nominal_value=-1.0)


@pytest.mark.parametrize(
    ("signal", "reason"),
    [
        ("material_deficit_in_acceptance", ReasonCode.MATERIAL_DEFICIT_IN_ACCEPTANCE_LINE),
        ("engine_considers_acceptance", ReasonCode.ENGINE_CONSIDERS_ACCEPTANCE),
        ("persists_under_deeper_search", ReasonCode.PATTERN_PERSISTS_DEEPER),
    ],
)
def test_each_signal_contributes_its_own_reason_and_weight(rules, signal, reason):
    signals = SacrificeSignals(**{signal: True})
    assert reasons_for(signals) == (reason,)
    assert sacrifice_confidence(signals, rules.sacrifice.confidence_weights) > 0.0


def test_scoring_inputs_reject_negative_counts():
    with pytest.raises(DomainError):
        ScoringInputs(
            expected_points_loss=0.0,
            sacrifice=SOUND_SACRIFICE,
            replies_preserving_evaluation=-1,
        )
    with pytest.raises(DomainError):
        ScoringInputs(
            expected_points_loss=0.0, sacrifice=SOUND_SACRIFICE, equivalent_alternatives=-1
        )


def test_quality_component_requires_a_positive_limit():
    broken = RuleSet(
        quality=QualityThresholds(max_expected_points_loss=0.0),
        selection=SelectionThresholds(safe_max_expected_points_loss=0.0),
    )
    with pytest.raises(DomainError):
        quality_component(0.0, broken)


def test_unknown_sacrifice_kind_still_scores_conservatively(rules):
    unknown_kind = replace(
        SOUND_SACRIFICE, kind=SacrificeKind.DECLINED_RECAPTURE, offered_piece_type=PieceType.KNIGHT
    )
    assert sacrifice_component(unknown_kind, 3.2, rules) > 0.0


def test_missing_robustness_evidence_scores_between_worst_and_best(rules):
    unknown = replace(
        scoring_inputs(),
        expected_points_drift=None,
        pv_overlap_plies=None,
        sacrifice_persisted=None,
    )
    worst = replace(
        scoring_inputs(),
        expected_points_drift=1.0,
        pv_overlap_plies=0,
        sacrifice_persisted=False,
    )
    best = scoring_inputs()
    assert (
        robustness_component(worst, rules)
        < robustness_component(unknown, rules)
        < robustness_component(best, rules)
    )


def test_strength_rejects_elo_outside_the_engine_range():
    with pytest.raises(DomainError):
        EngineStrength(key="baixo", label="baixo", elo=800, move_time_seconds=0.2)
    with pytest.raises(DomainError):
        EngineStrength(key="alto", label="alto", elo=9000, move_time_seconds=0.2)


def test_strength_rejects_non_positive_move_time():
    with pytest.raises(DomainError):
        EngineStrength(key="x", label="x", elo=None, move_time_seconds=0.0)


def test_strength_budget_prefers_nodes_when_given():
    by_nodes = EngineStrength(key="x", label="x", elo=None, move_time_seconds=1.0, nodes=5000)
    by_time = EngineStrength(key="y", label="y", elo=None, move_time_seconds=1.0)
    assert by_nodes.budget().nodes == 5000
    assert by_nodes.budget().is_deterministic is True
    assert by_time.budget().time_seconds == 1.0
    assert by_time.budget().is_deterministic is False


def test_unknown_strength_key_is_rejected():
    with pytest.raises(DomainError):
        strength_by_key("nao-existe")


def test_engine_session_without_a_binary_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.delenv("BRILLIANT_CHESS_STOCKFISH", raising=False)
    monkeypatch.delenv("STOCKFISH_PATH", raising=False)
    monkeypatch.setattr(
        "brilliant_chess.adapters.stockfish.diagnostics.LOCAL_ENGINE_DIR", tmp_path / "vazio"
    )
    monkeypatch.setattr("shutil.which", lambda _name: None)
    session = EngineSession(Settings())
    assert session.binary_path is None
    with pytest.raises(EngineNotFoundError):
        session.engine()
    session.close()


def test_game_store_rejects_unknown_games_and_evicts_the_oldest():
    store = GameStore(max_games=2)
    with pytest.raises(DomainError):
        store.get("inexistente")
    states = [
        play_game.start_game(f"jogo-{index}", STARTPOS, Color.WHITE, "clube") for index in range(3)
    ]
    for state in states:
        store.save(state)
    assert len(store) == 2
    with pytest.raises(DomainError):
        store.get("jogo-0")
    assert store.get("jogo-2").game_id == "jogo-2"


def test_cli_entrypoint_is_importable():
    assert callable(main)
    assert Position.from_fen(STARTPOS).fen == STARTPOS
