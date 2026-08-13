from __future__ import annotations

from dataclasses import replace

from brilliant_chess.adapters.board.service import PythonChessBoardService
from brilliant_chess.application.choose_brilliant_move import (
    StrictSearchBudget,
    choose_brilliant_move,
)
from brilliant_chess.domain.models import AnalysisBudget, Position
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


def engine_for(*, best_defense: bool = True, stability: bool = True) -> ScriptedEngine:
    board = PythonChessBoardService()
    position = Position.from_fen(POSITION_FEN)
    after = board.position_after(POSITION_FEN, ("h5h7",))
    script = {
        ScriptKey(position.fen, (), DISCOVERY.nodes): (
            evaluation("h5h7", Color.WHITE, centipawns=50, pv=("h5h7", "h8h7")),
        ),
        ScriptKey(position.fen, ("h5h7",), CONFIRMATION.nodes): (
            evaluation("h5h7", Color.WHITE, centipawns=50, pv=("h5h7", "h8h7")),
        ),
    }
    if best_defense:
        script[ScriptKey(after.fen, (), BEST_DEFENSE.nodes)] = (
            evaluation("h8h7", Color.BLACK, centipawns=-40, pv=("h8h7",)),
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


def test_missing_stability_evidence_is_conservative_near_a_threshold(rules):
    near_rules = replace(
        rules,
        prior_position=replace(rules.prior_position, max_expected_points_before=0.57),
    )
    choice = choose_brilliant_move(
        engine_for(stability=False),
        PythonChessBoardService(),
        Position.from_fen(POSITION_FEN),
        near_rules,
        budget(stability=None),
    )

    assert choice.move is None
    stability = next(
        gate for gate in choice.candidates[0].decision.gates if gate.gate_id is GateId.STABILITY
    )
    assert stability.status is GateStatus.INDETERMINATE


def test_eligible_audits_are_sorted_by_score_then_loss_then_uci(rules):
    first = replace(engine_for(), script={})
    board = PythonChessBoardService()
    position = Position.from_fen(POSITION_FEN)
    after = board.position_after(POSITION_FEN, ("h5h7",))
    first.script.update(
        {
            ScriptKey(position.fen, (), DISCOVERY.nodes): (
                evaluation("h5h7", Color.WHITE, centipawns=50, pv=("h5h7", "h8h7")),
                evaluation("h5g6", Color.WHITE, centipawns=50, pv=("h5g6",)),
            ),
            ScriptKey(position.fen, ("h5h7",), CONFIRMATION.nodes): (
                evaluation("h5h7", Color.WHITE, centipawns=50, pv=("h5h7", "h8h7")),
            ),
            ScriptKey(position.fen, ("h5g6",), CONFIRMATION.nodes): (
                evaluation("h5g6", Color.WHITE, centipawns=50, pv=("h5g6",)),
            ),
            ScriptKey(after.fen, (), BEST_DEFENSE.nodes): (
                evaluation("h8h7", Color.BLACK, centipawns=-40, pv=("h8h7",)),
            ),
            ScriptKey(position.fen, ("h5h7",), STABILITY.nodes): (
                evaluation("h5h7", Color.WHITE, centipawns=49, pv=("h5h7", "h8h7")),
            ),
        }
    )
    choice = choose_brilliant_move(
        first, board, position, rules, replace(budget(), multipv=2, max_candidates=2)
    )

    assert [audit.candidate.move_uci for audit in choice.candidates] == ["h5h7", "h5g6"]
