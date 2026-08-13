from __future__ import annotations

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application import choose_brilliant_move as selector
from brilliant_chess.application.analyze_position import Candidate, PositionAnalysis
from brilliant_chess.application.choose_brilliant_move import (
    CandidateAudit,
    StrictSearchBudget,
    choose_brilliant_move,
)
from brilliant_chess.domain.models import AnalysisBudget, EngineIdentity, Position
from brilliant_chess.domain.sacrifice import NO_SACRIFICE
from brilliant_chess.domain.scoring import BrilliantDecision, ScoreBreakdown
from brilliant_chess.domain.values import Color, GateId, GateStatus
from tests.fakes.scripted_engine import ScriptedEngine, ScriptKey, evaluation

POSITION_FEN = "7r/7p/8/7Q/8/8/8/6KR w - - 0 1"
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
        engine_for(), PythonChessBoardService(), Position.from_fen(POSITION_FEN), rules, budget()
    )

    assert choice.move is not None
    assert choice.move.uci == "h5h7"
    assert choice.selected is not None
    assert all(gate.status is GateStatus.PASSED for gate in choice.selected.decision.gates)


def test_best_defense_search_accepts_small_cross_search_ep_improvement(rules):
    choice = choose_brilliant_move(
        engine_for(best_defense_centipawns=-60),
        PythonChessBoardService(),
        Position.from_fen(POSITION_FEN),
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
        Position.from_fen(POSITION_FEN),
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
        Position.from_fen(POSITION_FEN),
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
        Position.from_fen(POSITION_FEN),
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
        Position.from_fen(POSITION_FEN),
        rules,
        budget(),
    )

    assert choice.move is None
    soundness = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.SOUNDNESS
    )
    assert soundness.status is GateStatus.FAILED


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

    choice = choose_brilliant_move(None, None, position, rules, budget())

    assert [audit.candidate.move_uci for audit in choice.candidates] == ["a1a2", "b1b2"]
    assert choice.move is not None
    assert choice.move.uci == "a1a2"


def _candidate(move_uci: str) -> Candidate:
    return Candidate(
        move_uci=move_uci,
        move_san=move_uci,
        rank=1,
        expected_points_after=0.5,
        expected_points_loss=0.01,
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
