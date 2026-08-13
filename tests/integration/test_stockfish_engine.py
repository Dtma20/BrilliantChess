"""Contrato do adapter contra o Stockfish real.

Lento e pulavel: exige o binario instalado. Orcamento em nos e Threads=1 para
reduzir variabilidade.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.adapters.stockfish.client import EngineOptions, StockfishEngine
from brilliant_chess.adapters.stockfish.diagnostics import locate_engine_binary
from brilliant_chess.application.analyze_position import AnalysisRequest, analyze_position
from brilliant_chess.bootstrap.config import load_settings
from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.models import AnalysisBudget, Move, Position
from brilliant_chess.domain.strength import strength_by_key
from brilliant_chess.domain.values import Color
from brilliant_chess.ports.engine import ChessEngine, PlayableEngine

pytestmark = pytest.mark.slow

BUDGET = AnalysisBudget(nodes=200_000)
BLACK_TO_MOVE = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
MATE_IN_TWO = "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1"
BLACK_IS_LOST = "6k1/5ppp/8/8/8/8/5PPP/R5K1 b - - 0 1"
CHECKMATE = "7k/5QQ1/8/8/8/8/8/7K b - - 0 1"


@pytest.fixture(scope="module")
def engine() -> Iterator[StockfishEngine]:
    settings = load_settings()
    info = locate_engine_binary(settings.resolved_engine_path())
    if not info.usable or info.path is None:
        pytest.skip("Stockfish nao encontrado; defina BRILLIANT_CHESS_STOCKFISH")
    instance = StockfishEngine(
        info.path, EngineOptions(threads=1, hash_mb=64), timeout_seconds=60.0
    )
    try:
        yield instance
    finally:
        instance.close()


def test_adapter_satisfies_both_ports(engine):
    assert isinstance(engine, ChessEngine)
    assert isinstance(engine, PlayableEngine)


def test_identity_is_complete_enough_for_the_cache_key(engine):
    identity = engine.identity()
    assert identity.name.lower() == "stockfish"
    assert identity.version
    assert len(identity.binary_sha256) == 64
    assert identity.nnue_name is not None
    assert identity.options["Threads"] == 1


def test_multipv_returns_distinct_moves_ordered_for_the_side_to_move(engine):
    results = engine.analyze(Position.from_fen(STARTING_FEN), BUDGET, multipv=4)
    assert len(results) == 4
    assert len({item.move_uci for item in results}) == 4
    points = [item.expected_points for item in results]
    assert points == sorted(points, reverse=True)
    assert all(item.evaluation.mover is Color.WHITE for item in results)


def test_point_of_view_follows_the_side_to_move(engine):
    """Mesma posicao vantajosa para as brancas, avaliada com pretas a jogar."""
    white = engine.analyze(Position.from_fen(MATE_IN_TWO), BUDGET, multipv=1)[0]
    black = engine.analyze(Position.from_fen(BLACK_IS_LOST), BUDGET, multipv=1)[0]
    assert white.evaluation.mover is Color.WHITE
    assert black.evaluation.mover is Color.BLACK
    assert white.expected_points > 0.5
    assert black.expected_points < 0.5


def test_wdl_is_available_and_drives_expected_points(engine):
    result = engine.analyze(Position.from_fen(STARTING_FEN), BUDGET, multipv=1)[0]
    assert result.evaluation.wdl is not None
    assert 0.0 <= result.expected_points <= 1.0


def test_root_moves_restrict_the_search(engine):
    results = engine.analyze(
        Position.from_fen(STARTING_FEN), BUDGET, multipv=1, root_moves=[Move("a2a3")]
    )
    assert [item.move_uci for item in results] == ["a2a3"]


def test_illegal_root_move_is_rejected(engine):
    with pytest.raises(EngineError):
        engine.analyze(
            Position.from_fen(STARTING_FEN), BUDGET, multipv=1, root_moves=[Move("e2e5")]
        )


def test_terminal_position_returns_no_analysis_lines(engine):
    """Stockfish legitimately omits a PV when the game is already over."""
    results = engine.analyze(Position.from_fen(CHECKMATE), BUDGET, multipv=1)
    assert results == ()


def test_principal_variation_is_legal_and_has_san(engine):
    result = engine.analyze(Position.from_fen(STARTING_FEN), BUDGET, multipv=1)[0]
    assert result.pv.moves_uci
    assert len(result.pv.moves_san) == len(result.pv.moves_uci)
    assert result.depth > 0
    assert result.nodes > 0


def test_play_move_returns_a_legal_move_at_reduced_strength(engine):
    board = PythonChessBoardService()
    position = Position.from_fen(STARTING_FEN)
    chosen = engine.play_move(position, strength_by_key("iniciante"))
    legal = {move.uci for move in board.view(STARTING_FEN, ()).legal_moves}
    assert chosen.uci in legal
    assert chosen.san


def test_analysis_stays_at_full_strength_after_a_weak_game_move(engine):
    """Limitar forca para jogar nao pode contaminar a analise seguinte."""
    engine.play_move(Position.from_fen(STARTING_FEN), strength_by_key("iniciante"))
    result = engine.analyze(Position.from_fen(MATE_IN_TWO), BUDGET, multipv=1)[0]
    assert result.expected_points > 0.5


def test_analyze_position_pipeline_ranks_candidates(engine):
    board = PythonChessBoardService()
    analysis = analyze_position(
        engine,
        board,
        AnalysisRequest(
            position=Position.from_fen(STARTING_FEN),
            discovery_budget=AnalysisBudget(nodes=100_000),
            confirmation_budget=AnalysisBudget(nodes=200_000),
            multipv=3,
            max_candidates=3,
        ),
    )
    assert [candidate.rank for candidate in analysis.candidates] == [1, 2, 3]
    assert analysis.candidates[0].expected_points_loss == 0.0
    assert all(candidate.expected_points_loss >= 0.0 for candidate in analysis.candidates)
    assert all(candidate.pv_san for candidate in analysis.candidates)


def test_black_to_move_analysis_is_not_inverted(engine):
    board = PythonChessBoardService()
    analysis = analyze_position(
        engine,
        board,
        AnalysisRequest(
            position=Position.from_fen(BLACK_TO_MOVE),
            discovery_budget=AnalysisBudget(nodes=100_000),
            confirmation_budget=AnalysisBudget(nodes=150_000),
            multipv=2,
            max_candidates=2,
        ),
    )
    assert analysis.side_to_move is Color.BLACK
    assert 0.3 < analysis.expected_points_before < 0.55


def test_close_is_idempotent():
    settings = load_settings()
    info = locate_engine_binary(settings.resolved_engine_path())
    assert info.path is not None
    disposable = StockfishEngine(info.path, EngineOptions(threads=1, hash_mb=16))
    disposable.close()
    disposable.close()
