"""Seletor ``strict_v1`` contra o Stockfish real.

Casos que so aparecem com motor de verdade: posicao terminal sem variante
principal, mate em um, peca deixada pendurada longe da casa de destino e empate
imediato que o motor nao pode ver porque nao recebe o historico da partida.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.adapters.stockfish.client import EngineOptions, StockfishEngine
from brilliant_chess.adapters.stockfish.diagnostics import locate_engine_binary
from brilliant_chess.application.choose_brilliant_move import (
    PositionHistory,
    StrictSearchBudget,
    choose_brilliant_move,
)
from brilliant_chess.bootstrap.config import load_settings
from brilliant_chess.domain.models import AnalysisBudget
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.values import GameStatus, GateId, GateStatus, SacrificeKind

pytestmark = pytest.mark.slow

#: A jogada certa e ``Qd8#``. Antes da regra de mate terminal, o seletor a
#: descartava por falta de defesa medida e preferia um xeque que repetia.
MATE_IN_ONE_FEN = "5k2/2pQ1rp1/2P5/7p/n1rbb2P/4B3/P4PP1/6K1 w - - 4 37"

#: Posicao apos 13...Bf5: a torre de b1 esta pendurada pela diagonal f5-b1 e
#: 14.e3 nao a salva. A casa de destino ``e3`` contem um peao, entao o detector
#: de oferta no destino nao ve nada.
LEFT_HANGING_ROOK_FEN = "r2qkb1r/1p3p1p/5np1/3Ppb2/7Q/p1N2N2/PP2PPPP/1RB1KB1R w Kkq - 2 14"

#: Rei e torre contra rei pelado: so 19 lances legais, entao o vaivem cabe na
#: lista de candidatas e o override de empate terminal fica observavel.
REPETITION_INITIAL_FEN = "7k/8/8/8/8/8/8/1R4K1 b - - 0 1"
REPETITION_HISTORY = ("h8g8", "b1b2", "g8h8", "b2b1", "h8g8", "b1b2", "g8h8")
REPETITION_FEN = "7k/8/8/8/8/8/1R6/6K1 w - - 7 5"

BUDGET = StrictSearchBudget(
    discovery=AnalysisBudget(nodes=80_000),
    confirmation=AnalysisBudget(nodes=150_000),
    best_defense=AnalysisBudget(nodes=150_000),
    stability=AnalysisBudget(nodes=250_000),
    multipv=6,
    max_candidates=6,
)

#: Orcamento reduzido para varrer todos os lances legais sem tornar o teste lento.
WIDE_BUDGET = StrictSearchBudget(
    discovery=AnalysisBudget(nodes=20_000),
    confirmation=AnalysisBudget(nodes=30_000),
    best_defense=AnalysisBudget(nodes=30_000),
    stability=AnalysisBudget(nodes=40_000),
    multipv=19,
    max_candidates=19,
)


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


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def _audit_for(choice, move_uci: str):
    return next(audit for audit in choice.candidates if audit.candidate.move_uci == move_uci)


def test_mate_in_one_is_chosen_and_never_raises_on_the_missing_pv(engine, board, rules: RuleSet):
    choice = choose_brilliant_move(engine, board, PositionHistory(MATE_IN_ONE_FEN), rules, BUDGET)

    chosen = choice.selected or choice.near_selected
    assert chosen is not None
    assert chosen.candidate.move_uci == "d7d8"
    assert chosen.terminal_status is GameStatus.CHECKMATE
    statuses = {gate.gate_id: gate.status for gate in chosen.decision.gates}
    assert statuses[GateId.SOUNDNESS] is GateStatus.PASSED
    assert statuses[GateId.STABILITY] is GateStatus.PASSED


def test_the_rook_left_hanging_on_b1_is_measured_as_evidence(engine, board, rules: RuleSet):
    choice = choose_brilliant_move(
        engine, board, PositionHistory(LEFT_HANGING_ROOK_FEN), rules, BUDGET
    )

    audited = _audit_for(choice, "e2e3")
    evidence = audited.decision.sacrifice
    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"
    assert audited.acceptance_san == ("Bxb1",)


def test_an_immediate_repetition_is_never_a_safe_continuation(engine, board, rules: RuleSet):
    """O motor nao recebe historico e ve mate; o tabuleiro ve empate imediato."""
    choice = choose_brilliant_move(
        engine,
        board,
        PositionHistory(REPETITION_INITIAL_FEN, REPETITION_HISTORY),
        rules,
        WIDE_BUDGET,
    )

    repeating = _audit_for(choice, "b2b1")
    assert repeating.terminal_status is GameStatus.DRAW_THREEFOLD_REPETITION
    assert repeating.candidate.expected_points_after == 0.5
    assert choice.near_selected is None or choice.near_selected.candidate.move_uci != "b2b1"
    assert choice.selected is None or choice.selected.candidate.move_uci != "b2b1"
