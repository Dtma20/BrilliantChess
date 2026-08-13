from __future__ import annotations

from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity, Move, Position
from brilliant_chess.domain.values import AnalysisState, Color
from brilliant_chess.ports.analysis_repository import (
    AnalysisCacheKey,
    StoredAnalysis,
    root_moves_fingerprint,
)
from brilliant_chess.ports.game_source import Game, GameMove
from tests.conftest import STARTPOS


def cache_key(**overrides) -> AnalysisCacheKey:
    base = {
        "fen": STARTPOS,
        "root_moves_uci": (),
        "engine_binary_sha256": "a" * 64,
        "engine_version": "18",
        "nnue_name": "nn-1234.nnue",
        "engine_options_fingerprint": "Threads=1;Hash=16",
        "budget_fingerprint": "nodes=100000",
        "multipv": 1,
        "wdl_mapping_version": "wdl_v1",
        "rule_set_version": "strict_v1",
    }
    return AnalysisCacheKey(**{**base, **overrides})


def test_cache_key_separates_budgets_and_rule_versions():
    assert cache_key() == cache_key()
    assert cache_key() != cache_key(budget_fingerprint="nodes=4000000")
    assert cache_key() != cache_key(rule_set_version="strict_v2")
    assert cache_key() != cache_key(multipv=12)
    assert cache_key() != cache_key(engine_binary_sha256="b" * 64)


def test_cache_key_is_hashable_for_use_as_a_dictionary_key():
    assert {cache_key(): "resultado"}[cache_key()] == "resultado"


def test_root_moves_fingerprint_is_order_independent():
    assert root_moves_fingerprint(None) == ()
    assert root_moves_fingerprint([Move("d2d4"), Move("e2e4")]) == ("d2d4", "e2e4")
    assert root_moves_fingerprint([Move("e2e4"), Move("d2d4")]) == ("d2d4", "e2e4")


def test_stored_analysis_carries_state_and_error():
    stored = StoredAnalysis(
        analysis_id="abc",
        state=AnalysisState.FAILED,
        key=cache_key(),
        identity=EngineIdentity(
            name="Stockfish", version="18", binary_sha256="a" * 64, nnue_name=None
        ),
        budget=AnalysisBudget(nodes=100_000),
        evaluations=(),
        error="processo encerrado",
    )
    assert stored.state is AnalysisState.FAILED
    assert stored.evaluations == ()
    assert stored.error == "processo encerrado"


def test_game_records_provenance_and_ply_count():
    game = Game(
        game_id="partida-1",
        headers={"White": "A", "Black": "B"},
        moves=(
            GameMove(
                ply=1,
                position_before=Position.from_fen(STARTPOS),
                move_uci="e2e4",
                move_san="e4",
            ),
        ),
        source="local_pgn",
        provenance={"file": "partida.pgn"},
    )
    assert game.ply_count == 1
    assert game.moves[0].position_before.side_to_move is Color.WHITE
    assert game.provenance["file"] == "partida.pgn"
