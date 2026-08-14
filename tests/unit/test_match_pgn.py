from __future__ import annotations

from dataclasses import replace

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
from brilliant_chess.domain.exchange import ExchangeDisposition, ExchangeEvidence
from brilliant_chess.domain.gates import GateResult
from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity
from brilliant_chess.domain.non_obviousness import (
    NonObviousnessCondition,
    NonObviousnessEvidence,
)
from brilliant_chess.domain.opening import (
    OpeningConfig,
    OpeningExitReason,
    OpeningIdentity,
    OpeningMode,
    OpeningMoveAudit,
    OpeningPhaseState,
)
from brilliant_chess.domain.sacrifice import NO_SACRIFICE, SacrificeEvidence
from brilliant_chess.domain.scoring import BrilliantDecision, ScoreBreakdown
from brilliant_chess.domain.values import (
    Color,
    GameStatus,
    GateId,
    GateStatus,
    PieceType,
    SacrificeKind,
)
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


def test_match_pgn_labels_a_strict_v2_fallback_with_the_moving_profile_policy(board):
    state = replace(
        match_state(),
        white=MatchProfile("maximo", MatchPolicy.STRICT_V2),
        moves=(
            MatchMove(Color.WHITE, "e2e4", "e4", SelectionKind.FALLBACK, None),
            *match_state().moves[1:],
        ),
    )

    text = build_match_pgn(
        state,
        board.view(STARTING_FEN, ()),
        board.view(STARTING_FEN, state.moves_uci),
        standard_fen=STARTING_FEN,
    )

    assert "{policy=strict_v2 selection=fallback reason=no_eligible_candidate}" in text


def test_cap_uses_draw_result_and_experimental_comment(board):
    state = match_state(capped=True)
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    text = build_match_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[Result "1/2-1/2"]' in text
    assert "{result=experimental_move_limit fullmoves=100}" in text
    assert text.rstrip().endswith("1/2-1/2")


def test_match_pgn_records_the_measured_sacrifice_evidence(board):
    evidence = SacrificeEvidence(
        detected=True,
        kind=SacrificeKind.LEFT_HANGING,
        offered_piece_square="b1",
        offered_piece_type=PieceType.ROOK,
        nominal_value=5.0,
        acceptance_moves=("f5b1",),
        confidence=0.55,
    )
    audit = MatchAudit(
        decision=BrilliantDecision(
            is_brilliant=False,
            selectable=False,
            score=48.0,
            gates=(
                GateResult(GateId.LEGAL, GateStatus.PASSED, True, True, "ok"),
                GateResult(GateId.SACRIFICE, GateStatus.FAILED, 5.0, 2.75, "confianca baixa"),
            ),
            sacrifice=evidence,
            breakdown=ScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
            rule_set_version="strict_v1",
        ),
        best_defense_uci="f5b1",
        stability_depth=28,
        best_defense_san="Bxb1",
        acceptance_san=("Bxb1",),
        defense_accepted=True,
        material_conceded=5.0,
    )
    state = replace(
        match_state(),
        moves=(
            MatchMove(Color.WHITE, "e2e4", "e4", SelectionKind.NEAR_BRILLIANT, audit),
            *match_state().moves[1:],
        ),
    )
    initial = board.view(STARTING_FEN, ())

    text = build_match_pgn(
        state,
        initial,
        board.view(STARTING_FEN, state.moves_uci),
        standard_fen=STARTING_FEN,
    )

    assert "selection=near_brilliant" in text
    assert "sacrifice=left_hanging@b1/rook" in text
    assert "accepted=yes" in text
    assert "conceded=5.00" in text
    assert "best_defense=Bxb1" in text
    assert "unmet=GATE_SACRIFICE_001" in text


def test_match_pgn_records_compact_v2_provenance_without_changing_v1_comments(board):
    exchange = ExchangeEvidence(
        disposition=ExchangeDisposition.CLEAN_EQUAL_TRADE,
        material_before=0.0,
        material_immediately_after=3.2,
        material_after_best_acceptance=-0.1,
        material_captured_by_candidate=3.2,
        material_lost_by_mover=3.3,
        material_captured_later_by_mover=1.7,
        net_material_concession=0.1,
        sequence_uci=("a2a3", "b4a3"),
        sequence_san=("a3", "Bxa3"),
        clean_trade=True,
        obvious_recapture=True,
        temporary_offer=True,
        favorable_trade=True,
        xray_recapture=True,
    )
    audit = MatchAudit(
        decision=BrilliantDecision(
            is_brilliant=False,
            selectable=False,
            score=48.0,
            gates=(),
            sacrifice=SacrificeEvidence(detected=False, exchange=exchange),
            breakdown=ScoreBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
            rule_set_version="strict_v2",
        ),
        best_defense_uci="b4a3",
        stability_depth=28,
        exchange=exchange,
        non_obviousness=NonObviousnessEvidence(
            shallow_rank=4,
            deep_rank=1,
            shallow_expected_points=0.51,
            deep_expected_points=0.6,
            expected_points_improvement=0.09,
            shallow_nodes=5_000,
            shallow_multipv=5,
            condition=NonObviousnessCondition.EP_IMPROVEMENT,
        ),
        detector_version="exchange_aware_v1",
        engine_identity=EngineIdentity("Stockfish", "17", "abc", "nn-123"),
        discovery_budget=AnalysisBudget(nodes=80_000),
        confirmation_budget=AnalysisBudget(nodes=200_000),
        best_defense_budget=AnalysisBudget(nodes=200_000),
        stability_budget=AnalysisBudget(nodes=400_000),
        shallow_budget=AnalysisBudget(nodes=5_000),
        shallow_multipv=5,
    )
    state = replace(
        match_state(),
        white=MatchProfile("maximo", MatchPolicy.STRICT_V2),
        moves=(
            MatchMove(Color.WHITE, "a2a3", "a3", SelectionKind.STRICT_V2, audit),
            *match_state().moves[1:],
        ),
    )

    text = build_match_pgn(
        state,
        board.view(STARTING_FEN, ()),
        board.view(STARTING_FEN, state.moves_uci),
        standard_fen=STARTING_FEN,
    )

    assert "policy=strict_v2 selection=strict_v2" in text
    assert "exchange=clean_equal_trade" in text
    assert "ex_before=0.00" in text
    assert "ex_after=3.20" in text
    assert "ex_accept=-0.10" in text
    assert "ex_captured=3.20" in text
    assert "ex_lost=3.30" in text
    assert "ex_later=1.70" in text
    assert "ex_net=0.10" in text
    assert "ex_uci=a2a3,b4a3" in text
    assert "ex_san=a3,Bxa3" in text
    assert "ex_clean=yes" in text
    assert "ex_obvious=yes" in text
    assert "ex_temporary=yes" in text
    assert "ex_favorable=yes" in text
    assert "ex_xray=yes" in text
    assert "non_obvious=ep_improvement" in text
    assert "shallow_ep=0.5100" in text
    assert "deep_ep=0.6000" in text
    assert "shallow_measure_nodes=5000" in text
    assert "shallow_measure_multipv=5" in text
    assert "detector=exchange_aware_v1" in text
    assert "binary_sha256=abc" in text
    assert "nnue=nn-123" in text
    assert "nodes=shallow:5000,discovery:80000,confirmation:200000" in text


def test_match_pgn_records_an_immediate_terminal_draw(board):
    audit = MatchAudit(
        decision=decision(12.0),
        best_defense_uci=None,
        stability_depth=None,
        terminal_status=GameStatus.DRAW_THREEFOLD_REPETITION,
    )
    state = replace(
        match_state(),
        moves=(
            MatchMove(Color.WHITE, "e2e4", "e4", SelectionKind.NEAR_BRILLIANT, audit),
            *match_state().moves[1:],
        ),
    )
    initial = board.view(STARTING_FEN, ())

    text = build_match_pgn(
        state,
        initial,
        board.view(STARTING_FEN, state.moves_uci),
        standard_fen=STARTING_FEN,
    )

    assert "end=draw_threefold_repetition" in text


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


def test_match_pgn_includes_opening_headers_and_comments(board):
    opening_audit = OpeningMoveAudit(
        opening_mode=OpeningMode.EXPLORATORY,
        source="suite",
        seed=42,
        opening_ply=1,
        planned_exit_ply=6,
        eco="B20",
        name="Sicilian Defense",
        variation="Bowdler Attack",
    )
    moves = (
        MatchMove(
            Color.WHITE,
            "e2e4",
            "e4",
            SelectionKind.OPENING_EXPLORATION,
            opening_audit=opening_audit,
        ),
        MatchMove(
            Color.BLACK,
            "c7c5",
            "c5",
            SelectionKind.OPENING_EXPLORATION,
            opening_audit=replace(opening_audit, opening_ply=2),
        ),
    )
    state = MatchState(
        match_id="opening_match",
        initial_fen=STARTING_FEN,
        current_fen=STARTING_FEN,
        white=MatchProfile("maximo", MatchPolicy.STRICT_V2),
        black=MatchProfile("iniciante", MatchPolicy.NORMAL),
        moves_uci=("e2e4", "c7c5"),
        moves_san=("e4", "c5"),
        moves=moves,
        opening_config=OpeningConfig(mode=OpeningMode.EXPLORATORY),
        opening_seed=42,
        opening_identity=OpeningIdentity(
            "sicilian_bowdler", "e4", "B20", "Sicilian Defense", "Bowdler Attack"
        ),
        opening_phase=OpeningPhaseState(
            active=False,
            mode=OpeningMode.EXPLORATORY,
            seed=42,
            planned_exit_ply=6,
            completed_opening_plies=6,
            current_phase="ended",
            exit_reason=OpeningExitReason.PLANNED_EXIT,
        ),
        opening_dataset_version="suite_v1",
    )
    initial = board.view(STARTING_FEN, ())
    current = board.view(STARTING_FEN, state.moves_uci)

    text = build_match_pgn(state, initial, current, standard_fen=STARTING_FEN)

    assert '[OpeningMode "exploratory"]' in text
    assert '[OpeningSeed "42"]' in text
    assert '[ECO "B20"]' in text
    assert '[Opening "Sicilian Defense"]' in text
    assert '[Variation "Bowdler Attack"]' in text
    assert '[OpeningExitReason "planned_exit"]' in text
    assert '[OpeningExitPly "6"]' in text
    assert '[OpeningDatasetVersion "suite_v1"]' in text
    assert "policy=opening_exploration" in text
    assert "selection=opening_exploration" in text
    assert "mode=exploratory" in text
    assert "eco=B20" in text
