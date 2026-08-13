from __future__ import annotations

import pytest

from brilliant_chess.adapters.board.service import STARTING_FEN, PythonChessBoardService
from brilliant_chess.application.play_match import (
    MatchAudit,
    MatchMove,
    MatchPolicy,
    MatchProfile,
    MatchState,
    SelectionKind,
)
from brilliant_chess.domain.sacrifice import NO_SACRIFICE
from brilliant_chess.domain.scoring import BrilliantDecision, ScoreBreakdown
from brilliant_chess.domain.values import Color
from brilliant_chess.interfaces.web.pgn import build_match_pgn


@pytest.fixture
def board() -> PythonChessBoardService:
    return PythonChessBoardService()


def decision(score: float) -> BrilliantDecision:
    return BrilliantDecision(
        is_brilliant=True,
        score=score,
        gates=(),
        sacrifice=NO_SACRIFICE,
        breakdown=ScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
        rule_set_version="strict_v1",
    )


def match_state(*, capped: bool = False) -> MatchState:
    moves_uci = ("e2e4", "e7e5") if capped else ("e2e4", "e7e5", "g1f3")
    moves = (
        MatchMove(
            Color.WHITE,
            "e2e4",
            "e4",
            SelectionKind.STRICT_V1,
            MatchAudit(decision(87.5), None, 20),
        ),
    )
    if capped:
        moves += (MatchMove(Color.BLACK, "e7e5", "e5", SelectionKind.NORMAL, None),)
    else:
        moves += (
            MatchMove(Color.BLACK, "e7e5", "e5", SelectionKind.NORMAL, None),
            MatchMove(Color.WHITE, "g1f3", "Nf3", SelectionKind.FALLBACK, None),
        )
    return MatchState(
        match_id="duelo123",
        initial_fen=STARTING_FEN,
        current_fen=STARTING_FEN,
        white=MatchProfile("maximo", MatchPolicy.STRICT_V1),
        black=MatchProfile("iniciante", MatchPolicy.NORMAL),
        moves_uci=moves_uci,
        moves_san=tuple(move.san for move in moves),
        moves=moves,
        max_plies=2 if capped else 200,
    )


def test_match_pgn_identifies_profiles_and_selection_comments(board):
    state = match_state()
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    text = build_match_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[White "Stockfish (Máximo, strict_v1)"]' in text
    assert '[Black "Stockfish (Iniciante, normal)"]' in text
    assert "{policy=strict_v1 selection=strict_v1 score=87.50 rule_set=strict_v1}" in text
    assert "{policy=normal selection=normal}" in text
    assert "{policy=strict_v1 selection=fallback reason=no_eligible_candidate}" in text


def test_cap_uses_draw_result_and_experimental_comment(board):
    state = match_state(capped=True)
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    text = build_match_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Result "1/2-1/2"]' in text
    assert "{result=experimental_move_limit fullmoves=100}" in text
    assert text.rstrip().endswith("1/2-1/2")


def test_match_pgn_includes_custom_fen_and_unfinished_result(board):
    fen = "8/5k2/8/8/8/8/8/R5K1 b - - 0 12"
    state = MatchState(
        match_id="custom",
        initial_fen=fen,
        current_fen=fen,
        white=MatchProfile("maximo", MatchPolicy.NORMAL),
        black=MatchProfile("iniciante", MatchPolicy.NORMAL),
    )
    initial = board.view(fen, ())

    text = build_match_pgn(state, initial, initial, standard_fen=STARTING_FEN)

    assert '[SetUp "1"]' in text
    assert f'[FEN "{fen}"]' in text
    assert '[Result "*"]' in text
