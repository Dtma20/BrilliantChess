from __future__ import annotations

import pytest

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application import choose_brilliant_move as selector
from brilliant_chess.application.analyze_position import Candidate, PositionAnalysis
from brilliant_chess.application.choose_brilliant_move import (
    CandidateAudit,
    PositionHistory,
    StrictSearchBudget,
    choose_brilliant_move,
)
from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.gates import GateResult
from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity, Position
from brilliant_chess.domain.non_obviousness import NonObviousnessCondition
from brilliant_chess.domain.rule_set import RuleSet
from brilliant_chess.domain.sacrifice import NO_SACRIFICE
from brilliant_chess.domain.scoring import BrilliantDecision, ScoreBreakdown
from brilliant_chess.domain.values import (
    Color,
    GameStatus,
    GateId,
    GateStatus,
    SacrificeKind,
)
from tests.fakes.scripted_engine import ScriptedEngine, ScriptKey, evaluation

POSITION_FEN = "7r/7p/8/7Q/8/8/8/6KR w - - 0 1"
MATE_IN_ONE_FEN = "5k2/2pQ1rp1/2P5/7p/n1rbb2P/4B3/P4PP1/6K1 w - - 4 37"
LEFT_HANGING_ROOK_FEN = "r2qkb1r/1p3p1p/5np1/3Ppb2/7Q/p1N2N2/PP2PPPP/1RB1KB1R w Kkq - 2 14"
REGRESSION_FEN = "r2qkb1r/pp2pppp/2n2n2/1Bpp4/3P4/4Pb1P/PP2PPPP/RN1QK2R w KQkq - 0 8"
SURPRISE_FEN = LEFT_HANGING_ROOK_FEN
#: Vaivem de torre e rei que faz a candidata ``b2b1`` completar a tripla
#: repeticao. Sem historico, nem o tabuleiro nem o motor veem o empate.
REPETITION_INITIAL_FEN = "7k/8/8/8/8/8/8/1R2Q1K1 b - - 0 1"
REPETITION_HISTORY = ("h8g8", "b1b2", "g8h8", "b2b1", "h8g8", "b1b2", "g8h8")
REPETITION_FEN = "7k/8/8/8/8/8/1R6/4Q1K1 w - - 7 5"
STALEMATE_FEN = "7k/8/8/8/8/8/8/5Q1K w - - 0 1"
DISCOVERY = AnalysisBudget(nodes=10)
CONFIRMATION = AnalysisBudget(nodes=20)
BEST_DEFENSE = AnalysisBudget(nodes=30)
STABILITY = AnalysisBudget(nodes=40)


def budget(*, stability: AnalysisBudget | None = STABILITY) -> StrictSearchBudget:
    return StrictSearchBudget(
        discovery=DISCOVERY,
        confirmation=CONFIRMATION,
        best_defense=BEST_DEFENSE,
        stability=stability,
        multipv=1,
        max_candidates=1,
    )


def v2_budget() -> StrictSearchBudget:
    return StrictSearchBudget(
        discovery=DISCOVERY,
        confirmation=CONFIRMATION,
        best_defense=BEST_DEFENSE,
        stability=STABILITY,
        multipv=3,
        max_candidates=3,
        shallow=AnalysisBudget(nodes=5_000),
        shallow_multipv=5,
    )


def engine_for(
    *,
    best_defense: bool = True,
    best_defense_centipawns: int = -40,
    stability: bool = True,
    candidate_pv: tuple[str, ...] = ("h5h7", "h8h7"),
) -> ScriptedEngine:
    board = PythonChessBoardService()
    position = Position.from_fen(POSITION_FEN)
    after = board.position_after(POSITION_FEN, ("h5h7",))
    script = {
        ScriptKey(position.fen, (), DISCOVERY.nodes): (
            evaluation("h5h7", Color.WHITE, centipawns=50, pv=candidate_pv),
        ),
        ScriptKey(position.fen, ("h5h7",), CONFIRMATION.nodes): (
            evaluation("h5h7", Color.WHITE, centipawns=50, pv=candidate_pv),
        ),
    }
    if best_defense:
        script[ScriptKey(after.fen, (), BEST_DEFENSE.nodes)] = (
            evaluation(
                "h8h7",
                Color.BLACK,
                centipawns=best_defense_centipawns,
                pv=("h8h7",),
            ),
        )
    if stability:
        script[ScriptKey(position.fen, ("h5h7",), STABILITY.nodes)] = (
            evaluation("h5h7", Color.WHITE, centipawns=49, pv=("h5h7", "h8h7"), depth=28),
        )
    return ScriptedEngine(script=script)


def test_selects_candidate_when_all_seven_gates_pass(rules):
    choice = choose_brilliant_move(
        engine_for(),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is not None
    assert choice.move.uci == "h5h7"
    assert choice.selected is not None
    assert all(gate.status is GateStatus.PASSED for gate in choice.selected.decision.gates)


def test_v2_rejects_bxc6_even_when_the_candidate_is_engine_best():
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("clean_exchange"),
        PythonChessBoardService(),
        PositionHistory(REGRESSION_FEN),
        RuleSet(id="strict_v2"),
        v2_budget(),
    )

    audit = next(item for item in choice.candidates if item.candidate.move_uci == "b5c6")
    assert audit.decision.selectable is False
    assert audit.decision.rule_set_version == "strict_v2"
    assert any(
        gate.gate_id is GateId.SACRIFICE and gate.status is GateStatus.FAILED
        for gate in audit.decision.gates
    )
    assert audit.exchange is not None


def test_v2_rejects_move_already_obvious_in_shallow_search():
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("shallow_obvious"),
        PythonChessBoardService(),
        PositionHistory(SURPRISE_FEN),
        RuleSet(id="strict_v2"),
        v2_budget(),
    )

    audit = choice.candidates[0]
    assert audit.non_obviousness is not None
    assert audit.non_obviousness.passed is False
    assert audit.decision.score > 80.0
    assert audit.decision.selectable is False


def test_v2_accepts_sound_move_that_improves_only_after_deeper_search():
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("deep_surprise"),
        PythonChessBoardService(),
        PositionHistory(SURPRISE_FEN),
        RuleSet(id="strict_v2"),
        v2_budget(),
    )

    assert choice.move is not None
    assert choice.selected is not None
    assert choice.selected.non_obviousness.condition is NonObviousnessCondition.EP_IMPROVEMENT
    assert choice.selected.non_obviousness.shallow_rank == 3
    assert choice.selected.non_obviousness.deep_rank == 2
    assert choice.selected.non_obviousness.expected_points_improvement == pytest.approx(
        0.0573, abs=0.001
    )
    assert choice.selected.detector_version == "exchange_aware_v1"
    assert choice.selected.engine_identity is not None
    assert choice.selected.engine_identity.name == "ScriptedEngine"
    assert choice.selected.shallow_budget == AnalysisBudget(nodes=5_000)
    assert choice.selected.confirmation_budget == CONFIRMATION


def test_v2_missing_engine_identity_is_conservative_instead_of_escaping():
    scripted = scripted_engine_for_v2_case("deep_surprise")
    engine = MissingIdentityEngine(script=scripted.script)

    choice = choose_brilliant_move(
        engine,
        PythonChessBoardService(),
        PositionHistory(SURPRISE_FEN),
        RuleSet(id="strict_v2"),
        v2_budget(),
    )

    assert choice.move is None
    assert choice.selected is None
    assert choice.candidates[0].engine_identity is None
    assert choice.candidates[0].decision.selectable is False


def test_v2_absent_shallow_rank_can_select_on_root_ep_improvement():
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("absent_from_shallow"),
        PythonChessBoardService(),
        PositionHistory(SURPRISE_FEN),
        RuleSet(id="strict_v2"),
        v2_budget(),
    )

    assert choice.selected is not None
    assert choice.selected.non_obviousness.shallow_rank is None
    assert choice.selected.non_obviousness.condition is NonObviousnessCondition.EP_IMPROVEMENT


def test_best_defense_search_accepts_small_cross_search_ep_improvement(rules):
    choice = choose_brilliant_move(
        engine_for(best_defense_centipawns=-60),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is not None
    soundness = next(
        gate for gate in choice.selected.decision.gates if gate.gate_id is GateId.SOUNDNESS
    )
    assert soundness.status is GateStatus.PASSED
    assert soundness.measured_value == 0.0


def test_best_defense_search_rejects_large_cross_search_disagreement(rules):
    choice = choose_brilliant_move(
        engine_for(best_defense_centipawns=-80),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is None
    soundness = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.SOUNDNESS
    )
    assert soundness.status is GateStatus.INDETERMINATE


def test_missing_best_defense_keeps_candidate_but_rejects_it(rules):
    choice = choose_brilliant_move(
        engine_for(best_defense=False),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is None
    assert len(choice.candidates) == 1
    soundness = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.SOUNDNESS
    )
    assert soundness.status is GateStatus.INDETERMINATE


def test_missing_stability_evidence_is_indeterminate_even_far_from_a_threshold(rules):
    choice = choose_brilliant_move(
        engine_for(stability=False),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(stability=None),
    )

    assert choice.move is None
    stability = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.STABILITY
    )
    assert stability.status is GateStatus.INDETERMINATE


def test_missing_candidate_pv_reply_is_not_proof_of_soundness(rules):
    choice = choose_brilliant_move(
        engine_for(candidate_pv=("h5h7",)),
        PythonChessBoardService(),
        PositionHistory(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is None
    soundness = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.SOUNDNESS
    )
    assert soundness.status is GateStatus.FAILED


def test_checkmate_has_soundness_and_stability_without_a_defense_line(rules):
    board = PythonChessBoardService()
    position = Position.from_fen(MATE_IN_ONE_FEN)
    engine = ScriptedEngine(
        script={
            ScriptKey(position.fen, (), DISCOVERY.nodes): (
                evaluation("d7d8", Color.WHITE, mate_in=1, pv=("d7d8",)),
            ),
            ScriptKey(position.fen, ("d7d8",), CONFIRMATION.nodes): (
                evaluation("d7d8", Color.WHITE, mate_in=1, pv=("d7d8",)),
            ),
        }
    )

    choice = choose_brilliant_move(engine, board, PositionHistory(MATE_IN_ONE_FEN), rules, budget())

    assert choice.near_selected is not None
    assert choice.near_selected.candidate.move_uci == "d7d8"
    statuses = {gate.gate_id: gate.status for gate in choice.near_selected.decision.gates}
    assert statuses[GateId.SOUNDNESS] is GateStatus.PASSED
    assert statuses[GateId.STABILITY] is GateStatus.PASSED


def _single_candidate_engine(
    fen: str, move_uci: str, *, centipawns: int, defense: tuple[str, int] | None = None
) -> ScriptedEngine:
    position = Position.from_fen(fen)
    script = {
        ScriptKey(position.fen, (), DISCOVERY.nodes): (
            evaluation(move_uci, position.side_to_move, centipawns=centipawns, pv=(move_uci,)),
        ),
        ScriptKey(position.fen, (move_uci,), CONFIRMATION.nodes): (
            evaluation(move_uci, position.side_to_move, centipawns=centipawns, pv=(move_uci,)),
        ),
        ScriptKey(position.fen, (move_uci,), STABILITY.nodes): (
            evaluation(move_uci, position.side_to_move, centipawns=centipawns, pv=(move_uci,)),
        ),
    }
    if defense is not None:
        after = PythonChessBoardService().position_after(fen, (move_uci,))
        script[ScriptKey(after.fen, (), BEST_DEFENSE.nodes)] = (
            evaluation(defense[0], after.side_to_move, centipawns=defense[1], pv=(defense[0],)),
        )
    return ScriptedEngine(script=script)


def test_immediate_threefold_repetition_is_not_a_safe_near_brilliant(rules):
    """O motor ve +9 porque nao recebe historico; o tabuleiro ve empate."""
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(REPETITION_FEN, "b2b1", centipawns=900),
        board,
        PositionHistory(REPETITION_INITIAL_FEN, REPETITION_HISTORY),
        rules,
        budget(),
    )

    assert choice.move is None
    assert choice.near_selected is None
    audited = choice.candidates[0]
    assert audited.candidate.expected_points_after == 0.5
    assert audited.candidate.mate_in is None
    assert audited.candidate.expected_points_loss > rules.selection.safe_max_expected_points_loss
    quality = next(gate for gate in audited.decision.gates if gate.gate_id is GateId.QUALITY)
    assert quality.status is GateStatus.FAILED


def test_a_terminal_draw_states_the_outcome_instead_of_missing_evidence(rules):
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(REPETITION_FEN, "b2b1", centipawns=900),
        board,
        PositionHistory(REPETITION_INITIAL_FEN, REPETITION_HISTORY),
        rules,
        budget(),
    )

    audited = choice.candidates[0]
    assert audited.terminal_status is GameStatus.DRAW_THREEFOLD_REPETITION
    soundness = next(gate for gate in audited.decision.gates if gate.gate_id is GateId.SOUNDNESS)
    assert soundness.status is GateStatus.PASSED
    assert "repetição" in soundness.explanation


def test_a_draw_that_concedes_nothing_stays_selectable_as_near_brilliant(rules):
    """Empate aceito de propria vontade: nao ha vitoria a entregar."""
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(REPETITION_FEN, "b2b1", centipawns=0),
        board,
        PositionHistory(REPETITION_INITIAL_FEN, REPETITION_HISTORY),
        rules,
        budget(),
    )

    assert choice.near_selected is not None
    assert choice.near_selected.candidate.move_uci == "b2b1"
    assert choice.near_selected.candidate.expected_points_after == 0.5


def test_immediate_stalemate_while_winning_is_rejected(rules):
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(STALEMATE_FEN, "f1f7", centipawns=900),
        board,
        PositionHistory(STALEMATE_FEN),
        rules,
        budget(),
    )

    assert choice.move is None
    assert choice.near_selected is None
    assert choice.candidates[0].terminal_status is GameStatus.STALEMATE


def test_the_selector_detects_a_piece_left_hanging_away_from_the_destination(rules):
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(
            LEFT_HANGING_ROOK_FEN, "e2e3", centipawns=30, defense=("f5b1", -20)
        ),
        board,
        PositionHistory(LEFT_HANGING_ROOK_FEN),
        rules,
        budget(),
    )

    audited = choice.candidates[0]
    evidence = audited.decision.sacrifice
    assert evidence.kind is SacrificeKind.LEFT_HANGING
    assert evidence.offered_piece_square == "b1"
    assert audited.acceptance_san == ("Bxb1",)
    assert audited.defense_accepted is True
    assert audited.material_conceded > 0.0


def test_the_root_position_comes_from_the_history(rules):
    """Caminho e posicao nao podem divergir: existe uma unica fonte de verdade."""
    board = PythonChessBoardService()

    choice = choose_brilliant_move(
        _single_candidate_engine(REPETITION_FEN, "b2b1", centipawns=0),
        board,
        PositionHistory(REPETITION_INITIAL_FEN, REPETITION_HISTORY),
        rules,
        budget(),
    )

    assert choice.candidates[0].candidate.move_uci == "b2b1"


def test_eligible_audits_break_a_full_tie_by_uci(rules, monkeypatch):
    position = Position.from_fen(POSITION_FEN)
    candidates = (
        _candidate("b1b2"),
        _candidate("a1a2"),
    )
    analysis = PositionAnalysis(
        position=position,
        side_to_move=Color.WHITE,
        engine=EngineIdentity("test", "1", "0" * 64, None),
        expected_points_before=0.5,
        candidates=candidates,
        warnings=(),
    )
    audits = {candidate.move_uci: _selectable_audit(candidate) for candidate in candidates}

    def fake_analyze(*_args):
        return analysis

    def fake_audit(_context, candidate):
        return audits[candidate.move_uci]

    monkeypatch.setattr(selector, "analyze_position", fake_analyze)
    monkeypatch.setattr(selector, "_audit_candidate", fake_audit)

    choice = choose_brilliant_move(
        None, PythonChessBoardService(), PositionHistory(POSITION_FEN), rules, budget()
    )

    assert [audit.candidate.move_uci for audit in choice.candidates] == ["a1a2", "b1b2"]
    assert choice.move is not None
    assert choice.move.uci == "a1a2"


def test_selects_safest_near_brilliant_when_none_is_strictly_eligible(rules, monkeypatch):
    position = Position.from_fen(POSITION_FEN)
    unsafe = _non_selectable_audit(
        _candidate("c1c2", expected_points_loss=0.005),
        score=95.0,
        failed_gates=(GateId.SACRIFICE, GateId.SOUNDNESS),
    )
    less_compelling = _non_selectable_audit(
        _candidate("b1b2", expected_points_loss=0.025),
        score=60.0,
        failed_gates=(GateId.SACRIFICE,),
    )
    closest = _non_selectable_audit(
        _candidate("a1a2", expected_points_loss=0.020),
        score=75.0,
        failed_gates=(GateId.SACRIFICE,),
    )
    candidates = (unsafe.candidate, less_compelling.candidate, closest.candidate)
    analysis = PositionAnalysis(
        position=position,
        side_to_move=Color.WHITE,
        engine=EngineIdentity("test", "1", "0" * 64, None),
        expected_points_before=0.5,
        candidates=candidates,
        warnings=(),
    )
    audits = {audit.candidate.move_uci: audit for audit in (unsafe, less_compelling, closest)}

    monkeypatch.setattr(selector, "analyze_position", lambda *_: analysis)
    monkeypatch.setattr(
        selector, "_audit_candidate", lambda _context, candidate: audits[candidate.move_uci]
    )

    choice = choose_brilliant_move(
        None, PythonChessBoardService(), PositionHistory(POSITION_FEN), rules, budget()
    )

    assert choice.move is None
    assert choice.selected is None
    assert choice.near_selected == closest


def test_near_brilliant_prioritizes_objective_quality_over_diagnostic_score(rules, monkeypatch):
    position = Position.from_fen(POSITION_FEN)
    objectively_best = _non_selectable_audit(
        _candidate("a1a2", expected_points_loss=0.001),
        score=43.0,
        failed_gates=(GateId.SACRIFICE,),
    )
    stylistic_but_worse = _non_selectable_audit(
        _candidate("b1b2", expected_points_loss=0.010),
        score=95.0,
        failed_gates=(GateId.SACRIFICE,),
    )
    audits = (objectively_best, stylistic_but_worse)
    analysis = PositionAnalysis(
        position=position,
        side_to_move=Color.WHITE,
        engine=EngineIdentity("test", "1", "0" * 64, None),
        expected_points_before=0.5,
        candidates=tuple(audit.candidate for audit in audits),
        warnings=(),
    )
    by_move = {audit.candidate.move_uci: audit for audit in audits}

    monkeypatch.setattr(selector, "analyze_position", lambda *_: analysis)
    monkeypatch.setattr(
        selector, "_audit_candidate", lambda _context, candidate: by_move[candidate.move_uci]
    )

    choice = choose_brilliant_move(
        None, PythonChessBoardService(), PositionHistory(POSITION_FEN), rules, budget()
    )

    assert choice.near_selected == objectively_best


def scripted_engine_for_v2_case(case: str) -> ScriptedEngine:
    board = PythonChessBoardService()
    if case == "clean_exchange":
        position = Position.from_fen(REGRESSION_FEN)
        candidates = (("b5c6", 40),)
        shallow = candidates
        confirmations = candidates
    elif case == "shallow_obvious":
        position = Position.from_fen(SURPRISE_FEN)
        candidates = (("e2e3", 40),)
        shallow = candidates
        confirmations = (("e2e3", 50),)
    elif case == "deep_surprise":
        position = Position.from_fen(SURPRISE_FEN)
        candidates = (("h4h6", 45), ("e2e3", 0), ("h4h5", -20))
        shallow = (("h4h6", 45), ("h4h5", 20), ("e2e3", 0))
        confirmations = (("h4h6", 45), ("e2e3", 40), ("h4h5", -20))
    elif case == "absent_from_shallow":
        position = Position.from_fen(SURPRISE_FEN)
        candidates = (("e2e3", 0),)
        shallow = (("h4h6", 45),)
        confirmations = (("e2e3", 40),)
    else:
        raise AssertionError(f"unknown v2 scripted case: {case}")

    script: dict[ScriptKey, tuple] = {
        ScriptKey(position.fen, (), DISCOVERY.nodes): tuple(
            evaluation(move, position.side_to_move, centipawns=cp, pv=(move,))
            for move, cp in candidates
        ),
        ScriptKey(position.fen, (), 5_000): tuple(
            evaluation(move, position.side_to_move, centipawns=cp, pv=(move,))
            for move, cp in shallow
        ),
    }
    if case == "absent_from_shallow":
        script[ScriptKey(position.fen, ("e2e3",), 5_000)] = (
            evaluation("e2e3", position.side_to_move, centipawns=0, pv=("e2e3",)),
        )
    for move, cp in confirmations:
        after = board.position_after(position.fen, (move,))
        defense = (
            "f5b1"
            if position.fen == SURPRISE_FEN and move == "e2e3"
            else board.view(after.fen, ()).legal_moves[0].uci
        )
        pv = (move, defense)
        script[ScriptKey(position.fen, (move,), CONFIRMATION.nodes)] = (
            evaluation(move, position.side_to_move, centipawns=cp, pv=pv),
        )
        script[ScriptKey(after.fen, (), BEST_DEFENSE.nodes)] = (
            evaluation(defense, after.side_to_move, centipawns=-40, pv=(defense,)),
        )
        script[ScriptKey(position.fen, (move,), STABILITY.nodes)] = (
            evaluation(move, position.side_to_move, centipawns=cp, pv=pv, depth=28),
        )
    return ScriptedEngine(script=script)


class MissingIdentityEngine(ScriptedEngine):
    def identity(self) -> EngineIdentity:
        raise EngineError("identity unavailable")


def _candidate(move_uci: str, *, expected_points_loss: float = 0.01) -> Candidate:
    return Candidate(
        move_uci=move_uci,
        move_san=move_uci,
        rank=1,
        expected_points_after=0.5,
        expected_points_loss=expected_points_loss,
        centipawns=0,
        mate_in=None,
        depth=20,
        nodes=100,
        pv_uci=(move_uci,),
        pv_san=(move_uci,),
    )


def _selectable_audit(candidate: Candidate) -> CandidateAudit:
    decision = BrilliantDecision(
        is_brilliant=True,
        selectable=True,
        score=50.0,
        gates=(),
        sacrifice=NO_SACRIFICE,
        breakdown=ScoreBreakdown(10.0, 10.0, 10.0, 10.0, 10.0),
        rule_set_version="strict_v1",
    )
    return CandidateAudit(candidate, decision, best_defense_uci=None, stability_depth=20)


def _non_selectable_audit(
    candidate: Candidate,
    *,
    score: float,
    failed_gates: tuple[GateId, ...],
) -> CandidateAudit:
    gates = tuple(
        GateResult(
            gate_id=gate_id,
            status=GateStatus.FAILED if gate_id in failed_gates else GateStatus.PASSED,
            measured_value=None,
            threshold=None,
            explanation="test",
        )
        for gate_id in GateId
    )
    decision = BrilliantDecision(
        is_brilliant=False,
        selectable=False,
        score=score,
        gates=gates,
        sacrifice=NO_SACRIFICE,
        breakdown=ScoreBreakdown(10.0, 10.0, 10.0, 10.0, 10.0),
        rule_set_version="strict_v1",
    )
    return CandidateAudit(candidate, decision, best_defense_uci=None, stability_depth=20)
