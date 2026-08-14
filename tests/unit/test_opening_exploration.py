from __future__ import annotations

import random
from dataclasses import replace

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.adapters.openings.suite import DEFAULT_SUITE_PATH, load_opening_suite
from brilliant_chess.application.opening_exploration import OpeningSelector
from brilliant_chess.domain.models import (
    AnalysisBudget,
    MoveEvaluation,
    NormalizedEvaluation,
    Position,
    PrincipalVariation,
)
from brilliant_chess.domain.opening import (
    OpeningConfig,
    OpeningExitReason,
    OpeningLine,
    OpeningMode,
)
from brilliant_chess.domain.values import Color
from brilliant_chess.ports.engine import ChessEngine


class FakeEngine(ChessEngine):
    def __init__(self, evals: tuple[MoveEvaluation, ...] = (), should_fail: bool = False) -> None:
        self.evals = evals
        self.should_fail = should_fail
        self.calls: list[dict] = []

    def analyze(
        self,
        position: Position,
        budget: AnalysisBudget,
        multipv: int = 1,
        root_moves: tuple[str, ...] | None = None,
    ):
        del root_moves
        if self.should_fail:
            raise RuntimeError("Engine crashed")
        self.calls.append({"position": position, "budget": budget, "multipv": multipv})
        return self.evals


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


@pytest.fixture
def full_suite() -> tuple[OpeningLine, ...]:
    return load_opening_suite(DEFAULT_SUITE_PATH)


@pytest.fixture
def selector(full_suite, board) -> OpeningSelector:
    return OpeningSelector(full_suite, board)


@pytest.fixture
def config() -> OpeningConfig:
    return OpeningConfig(
        mode=OpeningMode.EXPLORATORY,
        seed=42,
        min_fullmove=4,
        max_fullmove=10,
        multipv=6,
        max_ep_loss=0.08,
        temperature=0.04,
        extra_plies=3,
        budget_nodes=5000,
    )


def test_same_seed_reproduces_line_and_exit(selector, config):
    first_line, first_exit, first_reason = selector.choose(STARTING_FEN, config.with_seed(42))
    second_line, second_exit, second_reason = selector.choose(STARTING_FEN, config.with_seed(42))

    assert first_line is not None
    assert second_line is not None
    assert first_line.line_id == second_line.line_id
    assert first_exit == second_exit
    assert first_reason is None
    assert second_reason is None


def test_fixed_different_seeds_produce_multiple_sequences(selector, config):
    line_ids = {
        selector.choose(STARTING_FEN, config.with_seed(seed))[0].line_id
        for seed in (2, 3, 5, 7, 11, 13, 17, 19, 23)
    }
    assert len(line_ids) >= 2


def test_incompatible_initial_fen_returns_no_compatible_line(selector, config):
    endgame_fen = "8/8/8/8/8/8/4k3/4K3 w - - 0 1"
    line, exit_ply, reason = selector.choose(endgame_fen, config)
    assert line is None
    assert exit_ply == 0
    assert reason is OpeningExitReason.NO_COMPATIBLE_LINE


def test_mode_off_returns_disabled(selector, config):
    _line, _exit_ply, _reason = selector.choose(STARTING_FEN, config.with_seed(42))
    off_config = replace(config, mode=OpeningMode.OFF)
    line_off, exit_off, reason_off = selector.choose(STARTING_FEN, off_config)
    assert line_off is None
    assert exit_off == 0
    assert reason_off is OpeningExitReason.DISABLED


def test_session_usage_weighting_penalizes_previously_used_line(selector, config):
    initial_line, _, _ = selector.choose(STARTING_FEN, config.with_seed(42))
    assert initial_line is not None

    usage = {initial_line.line_id: 1000}
    other_line, _, _ = selector.choose(STARTING_FEN, config.with_seed(42), usage_counts=usage)
    assert other_line is not None
    assert other_line.line_id != initial_line.line_id


def test_no_candidate_surviving_ep_cutoff_ends_phase(selector, config, board):
    pos = board.view(STARTING_FEN, ()).position
    empty_engine = FakeEngine(evals=())
    move, audit, reason = selector.sample_multipv_move(
        pos, empty_engine, config, random.Random(42), opening_ply=8, planned_exit_ply=12
    )
    assert move is None
    assert audit is None
    assert reason is OpeningExitReason.ENGINE_ERROR


def test_multipv_sampling_selects_legal_move_and_produces_audit(selector, config, board):
    pos = board.view(STARTING_FEN, ()).position
    evals = (
        MoveEvaluation(
            move_uci="e2e4",
            move_san="e4",
            evaluation=NormalizedEvaluation(Color.WHITE, 20, None, 0.55),
            pv=PrincipalVariation(("e2e4",), ("e4",)),
            depth=10,
            nodes=5000,
            multipv_rank=1,
        ),
        MoveEvaluation(
            move_uci="d2d4",
            move_san="d4",
            evaluation=NormalizedEvaluation(Color.WHITE, 15, None, 0.53),
            pv=PrincipalVariation(("d2d4",), ("d4",)),
            depth=10,
            nodes=5000,
            multipv_rank=2,
        ),
    )
    engine = FakeEngine(evals=evals)
    move, audit, reason = selector.sample_multipv_move(
        pos,
        engine,
        config,
        random.Random(42),
        opening_ply=1,
        planned_exit_ply=8,
        eco="C50",
        name="Italian Game",
    )
    assert move is not None
    assert move.uci in {"e2e4", "d2d4"}
    assert audit is not None
    assert audit.opening_mode is OpeningMode.EXPLORATORY
    assert audit.eco == "C50"
    assert audit.source == "multipv_sampling"
    assert audit.search_budget.nodes == config.budget_nodes
    assert reason is None
