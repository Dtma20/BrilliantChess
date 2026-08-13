from __future__ import annotations

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application.analyze_position import AnalysisRequest, analyze_position
from brilliant_chess.domain.models import AnalysisBudget, Position
from brilliant_chess.domain.values import Color, WarningCode
from tests.fakes.scripted_engine import ScriptedEngine, ScriptKey, evaluation

DISCOVERY = AnalysisBudget(nodes=1_000)
CONFIRMATION = AnalysisBudget(nodes=10_000)


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def request_for(position: Position, multipv: int = 3) -> AnalysisRequest:
    return AnalysisRequest(
        position=position,
        discovery_budget=DISCOVERY,
        confirmation_budget=CONFIRMATION,
        multipv=multipv,
        max_candidates=multipv,
    )


def engine_with(discovery, confirmations) -> ScriptedEngine:
    script = {ScriptKey(STARTING_FEN, (), DISCOVERY.nodes): discovery}
    for uci, item in confirmations.items():
        script[ScriptKey(STARTING_FEN, (uci,), CONFIRMATION.nodes)] = (item,)
    return ScriptedEngine(script=script)


def test_confirmation_defines_the_ranking(board):
    """Discovery poe d2d4 em primeiro; a confirmacao individual desmente."""
    engine = engine_with(
        discovery=(
            evaluation("d2d4", Color.WHITE, centipawns=60, rank=1),
            evaluation("e2e4", Color.WHITE, centipawns=50, rank=2),
        ),
        confirmations={
            "d2d4": evaluation("d2d4", Color.WHITE, centipawns=20),
            "e2e4": evaluation("e2e4", Color.WHITE, centipawns=55),
        },
    )
    analysis = analyze_position(
        engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=2)
    )
    assert [candidate.move_uci for candidate in analysis.candidates] == ["e2e4", "d2d4"]
    assert analysis.candidates[0].rank == 1
    assert analysis.candidates[0].discovery_rank == 2
    assert WarningCode.RANK_CHANGED_AFTER_CONFIRMATION in analysis.warnings


def test_expected_points_loss_is_measured_against_the_confirmed_best(board):
    engine = engine_with(
        discovery=(
            evaluation("e2e4", Color.WHITE, centipawns=50, rank=1),
            evaluation("d2d4", Color.WHITE, centipawns=40, rank=2),
        ),
        confirmations={
            "e2e4": evaluation("e2e4", Color.WHITE, centipawns=50),
            "d2d4": evaluation("d2d4", Color.WHITE, centipawns=40),
        },
    )
    analysis = analyze_position(
        engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=2)
    )
    best, second = analysis.candidates
    assert best.expected_points_loss == 0.0
    assert second.expected_points_loss > 0.0
    assert analysis.expected_points_before == best.expected_points_after


def test_confirmation_uses_root_moves_one_candidate_at_a_time(board):
    engine = engine_with(
        discovery=(
            evaluation("e2e4", Color.WHITE, centipawns=50, rank=1),
            evaluation("d2d4", Color.WHITE, centipawns=40, rank=2),
        ),
        confirmations={
            "e2e4": evaluation("e2e4", Color.WHITE, centipawns=50),
            "d2d4": evaluation("d2d4", Color.WHITE, centipawns=40),
        },
    )
    analyze_position(engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=2))
    confirmation_calls = [call for call in engine.calls if call.root_moves]
    assert [call.root_moves for call in confirmation_calls] == [("e2e4",), ("d2d4",)]
    assert all(call.budget == CONFIRMATION for call in confirmation_calls)
    assert all(call.multipv == 1 for call in confirmation_calls)


def test_mate_produces_a_warning_and_the_top_rank(board):
    engine = engine_with(
        discovery=(
            evaluation("e2e4", Color.WHITE, mate_in=3, rank=1),
            evaluation("d2d4", Color.WHITE, centipawns=900, rank=2),
        ),
        confirmations={
            "e2e4": evaluation("e2e4", Color.WHITE, mate_in=3),
            "d2d4": evaluation("d2d4", Color.WHITE, centipawns=900),
        },
    )
    analysis = analyze_position(
        engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=2)
    )
    assert analysis.candidates[0].move_uci == "e2e4"
    assert analysis.candidates[0].mate_in == 3
    assert WarningCode.MATE_SCORE_PRESENT in analysis.warnings


def test_missing_wdl_is_reported_as_a_fallback(board):
    engine = engine_with(
        discovery=(evaluation("e2e4", Color.WHITE, centipawns=30, rank=1),),
        confirmations={"e2e4": evaluation("e2e4", Color.WHITE, centipawns=30)},
    )
    analysis = analyze_position(
        engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=1)
    )
    assert WarningCode.WDL_UNAVAILABLE_FALLBACK_USED in analysis.warnings


def test_wdl_when_available_is_used_without_warning(board):
    engine = engine_with(
        discovery=(evaluation("e2e4", Color.WHITE, centipawns=30, wdl=(300, 600, 100), rank=1),),
        confirmations={"e2e4": evaluation("e2e4", Color.WHITE, centipawns=30, wdl=(300, 600, 100))},
    )
    analysis = analyze_position(
        engine, board, request_for(Position.from_fen(STARTING_FEN), multipv=1)
    )
    assert WarningCode.WDL_UNAVAILABLE_FALLBACK_USED not in analysis.warnings
    assert analysis.candidates[0].expected_points_after == pytest.approx(0.6)
