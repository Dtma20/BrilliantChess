"""Testes de contrato do port ``ChessEngine``.

Rodam contra o ``ScriptedEngine`` agora e devem ser reaproveitados pelo adapter
real do Stockfish na Entrega 2, sem alterar as asserces.
"""

from __future__ import annotations

import pytest

from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.models import AnalysisBudget, Move, Position
from brilliant_chess.domain.values import Color
from brilliant_chess.ports.engine import ChessEngine
from tests.conftest import BLACK_TO_MOVE_FEN, STARTPOS
from tests.fakes.scripted_engine import ScriptedEngine, ScriptKey, evaluation

BUDGET = AnalysisBudget(nodes=100_000)


@pytest.fixture
def engine() -> ScriptedEngine:
    return ScriptedEngine(
        script={
            ScriptKey(STARTPOS): (
                evaluation("e2e4", Color.WHITE, centipawns=35, rank=1),
                evaluation("d2d4", Color.WHITE, centipawns=30, rank=2),
            ),
            ScriptKey(STARTPOS, ("d2d4",)): (
                evaluation("d2d4", Color.WHITE, centipawns=28, rank=1),
            ),
            ScriptKey(BLACK_TO_MOVE_FEN): (
                evaluation("c7c5", Color.BLACK, centipawns=-20, rank=1),
            ),
        }
    )


def test_scripted_engine_satisfies_the_port(engine):
    assert isinstance(engine, ChessEngine)


def test_identity_exposes_everything_the_cache_key_needs(engine):
    identity = engine.identity()
    assert identity.name
    assert identity.version
    assert len(identity.binary_sha256) == 64
    assert "Threads" in identity.options


def test_evaluations_are_from_the_point_of_view_of_the_side_to_move(engine):
    white = engine.analyze(Position.from_fen(STARTPOS), BUDGET, multipv=2)
    black = engine.analyze(Position.from_fen(BLACK_TO_MOVE_FEN), BUDGET)
    assert all(item.evaluation.mover is Color.WHITE for item in white)
    assert all(item.evaluation.mover is Color.BLACK for item in black)


def test_results_are_ordered_by_quality_for_the_side_to_move(engine):
    results = engine.analyze(Position.from_fen(STARTPOS), BUDGET, multipv=2)
    points = [item.expected_points for item in results]
    assert points == sorted(points, reverse=True)


def test_root_moves_restrict_the_search(engine):
    results = engine.analyze(Position.from_fen(STARTPOS), BUDGET, root_moves=[Move("d2d4")])
    assert [item.move_uci for item in results] == ["d2d4"]
    assert engine.calls[-1].root_moves == ("d2d4",)


def test_engine_failure_is_reported_as_domain_engine_error(engine):
    engine.crashes_remaining = 1
    with pytest.raises(EngineError):
        engine.analyze(Position.from_fen(STARTPOS), BUDGET)
    assert engine.analyze(Position.from_fen(STARTPOS), BUDGET)


def test_close_is_idempotent(engine):
    engine.close()
    engine.close()
    assert engine.close_count == 2


def test_unknown_position_raises_instead_of_inventing_a_result(engine):
    unknown = Position.from_fen("8/8/8/8/8/8/8/K6k w - - 0 1")
    with pytest.raises(EngineError):
        engine.analyze(unknown, BUDGET)
