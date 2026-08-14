# `strict_v2` Exchange-Aware Classifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a separately versioned `strict_v2` classifier that uses legal exchange evidence, rejects clean trades, adds non-obviousness, and preserves historical `strict_v1` behavior.

**Architecture:** Keep the existing v1 detector and seven-gate path intact. Add typed exchange traces to the board port, a pure exchange evaluator, an eight-gate v2 path, and policy-specific rule-set resolution in the container. Extend audit/API/PGN provenance without making the domain import `python-chess`.

**Tech Stack:** Python 3.12, dataclasses and `StrEnum`, `python-chess` only in the board adapter, Pydantic/YAML at bootstrap, pytest fakes with fixed node budgets, FastAPI schemas, and the existing React/Vite frontend.

**Spec:** `docs/superpowers/specs/2026-08-13-strict-v2-design.md`

## Global Constraints

- `strict_v1` remains selectable and its historical detector, thresholds, seven gates, and audit records are not reinterpreted.
- `normal` policy remains unchanged.
- `strict_v2` is never presented as equivalent to Chess.com Game Review.
- The domain imports neither `python-chess`, Pydantic, CLI code, subprocesses, nor web code.
- All analysis budgets in tests and laboratory configuration use nodes, not time.
- Mandatory gates are evaluated before scoring; a score cannot rescue a failed gate.
- Existing uncommitted PGN/FEN and laboratory UI changes are preserved and not reformatted.
- The regression FEN and golden fixtures are not changed to accommodate implementation failures.

### Task 1: Add pure v2 evidence, thresholds, and gate contracts

**Files:**

- Create: `src/brilliant_chess/domain/exchange.py`
- Create: `src/brilliant_chess/domain/non_obviousness.py`
- Modify: `src/brilliant_chess/domain/values.py`
- Modify: `src/brilliant_chess/domain/sacrifice.py`
- Modify: `src/brilliant_chess/domain/rule_set.py`
- Modify: `src/brilliant_chess/domain/gates.py`
- Modify: `src/brilliant_chess/domain/scoring.py`
- Test: `tests/unit/test_sacrifice.py`
- Test: `tests/unit/test_gates.py`
- Test: `tests/unit/test_scoring.py`

**Interfaces:**

- Consumes: existing `Piece`, `PiecePlacement`, `MaterialValues`, `GateResult`, and `RuleSet` types.
- Produces: `ExchangeDisposition`, `ExchangePly`, `ExchangeTrace`, `ExchangeEvidence`, `NonObviousnessEvidence`, `NonObviousnessThresholds`, and `GateId.NON_OBVIOUS`.

- [ ] **Step 1: Write failing pure-domain tests.**

Add tests with the following wished-for contracts before implementation:

```python
@pytest.fixture
def rules_v2() -> RuleSet:
    return RuleSet(id="strict_v2")


def test_v2_gate_rejects_clean_equal_exchange(rules_v2):
    evidence = SacrificeEvidence(
        detected=False,
        exchange=ExchangeEvidence(
            disposition=ExchangeDisposition.CLEAN_EQUAL_TRADE,
            material_before=0.0,
            material_immediately_after=3.2,
            material_after_best_acceptance=-0.1,
            material_captured_by_candidate=3.2,
            material_lost_by_mover=3.3,
            net_material_concession=0.1,
            clean_trade=True,
            obvious_recapture=True,
        ),
    )
    result = gate_sacrifice_v2(evidence, rules_v2.sacrifice)
    assert result.status is GateStatus.FAILED
    assert "troca limpa" in result.explanation
    assert "não satisfaz" in result.explanation


def test_v2_non_obviousness_accepts_deep_surprise(rules_v2):
    evidence = NonObviousnessEvidence(
        shallow_rank=5,
        deep_rank=2,
        shallow_expected_points=0.52,
        deep_expected_points=0.57,
        expected_points_improvement=0.05,
        shallow_nodes=5_000,
        shallow_multipv=5,
        condition=NonObviousnessCondition.EP_IMPROVEMENT,
    )
    assert gate_non_obviousness(evidence, rules_v2.non_obviousness).passed


def test_v2_score_does_not_override_failed_mandatory_gate(rules_v2):
    inputs = ScoringInputs(
        expected_points_loss=0.0,
        sacrifice=SacrificeEvidence(detected=False),
    )
    decision = decide(
        (GateResult(GateId.NON_OBVIOUS, GateStatus.FAILED, False, True, "obvious"),),
        inputs,
        rules_v2,
    )
    assert decision.selectable is False
    assert decision.is_brilliant is False
```

- [ ] **Step 2: Run the focused tests and verify the expected RED state.**

Run: `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

Expected: collection or assertion failures because the new v2 types and gate do not exist; do not modify existing v1 expectations to make this pass.

- [ ] **Step 3: Implement the minimal pure types and v2 gate.**

Add `ExchangeDisposition` values for `none`, `destination_offer`,
`left_hanging`, `exchange_sacrifice`, `declined_recapture`,
`clearance_or_deflection`, `clean_equal_trade`, `favorable_trade`,
`obvious_recapture`, and `temporary_offer`. Keep `SacrificeKind` limited to
actual sacrifice kinds used by scoring. Add `ExchangeEvidence` as a typed,
serializable value object with nullable acceptance balance and the required
material/sequence flags. Add `exchange` to `SacrificeEvidence`; v1 callers
continue to receive `exchange=None`.

Add `NonObviousnessCondition` and `NonObviousnessEvidence` with a boolean
`passed` property. Add v2-only fields to `SacrificeThresholds`:
`min_net_material_concession=1.0`, `equal_trade_tolerance=0.5`, and
`exchange_search_plies=8`. Add `NonObviousnessThresholds` with
`shallow_nodes=5000`, `shallow_multipv=5`, `min_expected_points_improvement=0.03`,
`max_obvious_shallow_rank=2`, `max_confirmed_rank=3`, and
`min_rank_improvement=2`.

Extend `GateInputs` with an optional `non_obviousness` field and keep it
absent for v1 callers. The v2 evaluator treats absent or indeterminate
non-obviousness evidence as a failed mandatory gate; the v1 seven-gate result
remains shape-compatible.

Keep `evaluate_gates()` returning the current seven results for `strict_v1`.
For a rule set whose id is `strict_v2`, append exactly one
`GATE_NON_OBVIOUS_001` result and use `gate_sacrifice_v2()` for the sacrifice
gate. The v2 explanation for a clean trade must contain the Portuguese text
`troca limpa de material aproximadamente igual` and `não satisfaz o portão de sacrifício`.

Update scoring only so the sacrifice component uses `net_material_concession`
from exchange evidence when present; `decide()` must continue to derive
`selectable` exclusively from `all_gates_passed()`.

- [ ] **Step 4: Run the focused tests and verify GREEN.**

Run: `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

Expected: all focused tests pass, including the existing v1 tests and the new v2 tests.

- [ ] **Step 5: Refactor only after GREEN.**

Keep exchange disposition and non-obviousness evidence in separate modules;
remove duplicated threshold checks only if all focused tests remain green.

### Task 2: Add typed exchange traces behind the board port

**Files:**

- Modify: `src/brilliant_chess/ports/board.py`
- Modify: `src/brilliant_chess/adapters/board/service.py`
- Test: `tests/unit/test_board_service.py`
- Test: `tests/unit/test_ports.py`

**Interfaces:**

- Consumes: `Position`, `Move`, `PositionSnapshot`, `Piece`, and a candidate history.
- Produces: `BoardService.exchange_lines(initial_fen, moves_uci, candidate_move, max_plies) -> tuple[ExchangeTrace, ...]`.

- [ ] **Step 1: Write failing adapter/port tests.**

```python
REGRESSION_FEN = "r2qkb1r/pp2pppp/2n2n2/1Bpp4/3P4/4Pb1P/PPPB1PP1/RN1QK2R w KQkq - 0 8"


def test_exchange_trace_contains_candidate_and_bxc6_recapture(board):
    traces = board.exchange_lines(REGRESSION_FEN, (), "b5c6", max_plies=4)
    assert traces
    line = traces[0]
    assert line.candidate.uci == "b5c6"
    assert line.acceptance_moves[0].move.uci == "b7c6"
    assert line.acceptance_moves[0].move.san == "bxc6"


def test_exchange_trace_follows_xray_recapture(board):
    traces = board.exchange_lines(
        "7k/8/4p3/3p4/8/8/3Q4/3R2K1 w - - 0 1",
        (),
        "d2d5",
        max_plies=4,
    )
    assert any(
        tuple(step.move.uci for step in trace.acceptance_moves[:2]) == ("e6d5", "d1d5")
        for trace in traces
    )
```

- [ ] **Step 2: Run the tests and verify RED for the missing port method.**

Run: `uv run pytest tests/unit/test_board_service.py tests/unit/test_ports.py -q`

Expected: failure because `BoardService.exchange_lines` is not implemented.

- [ ] **Step 3: Implement the adapter traversal.**

Add `ExchangePly` and `ExchangeTrace` to `domain/exchange.py`. The trace stores
the root snapshot, immediate post-candidate snapshot, target square, candidate
move, and a tuple of acceptance `ExchangePly`s. In
`PythonChessBoardService`, normalize and push the candidate, then recursively
enumerate legal capture moves whose destination is the candidate target square.
Sort every branch by UCI, stop at `max_plies`, and stop a branch when no legal
capture remains. Capture the removed piece by comparing the before/after
snapshots, including en-passant removal. Preserve SAN from the board before
each push. Return no traces when the candidate is illegal. For a legal
candidate with no immediate acceptance, return one deterministic trace with an
empty `acceptance_moves` tuple so the evaluator can distinguish a declined
offer or left-hanging piece from an invalid move. Ordinary move validation
still raises the existing domain errors.

The implementation must not expose `chess.Board`, `chess.Move`, or any adapter
class through the port return value.

- [ ] **Step 4: Run adapter and import-boundary tests.**

Run: `uv run pytest tests/unit/test_board_service.py tests/unit/test_ports.py -q`

Expected: PASS, including legal UCI/SAN sequence, deterministic ordering, and
the repository's banned-import check for `domain/`.

### Task 3: Implement exchange-aware sacrifice evaluation

**Files:**

- Create: `src/brilliant_chess/application/exchange_sacrifice.py`
- Modify: `src/brilliant_chess/application/sacrifice_detector.py` only to keep v1 comments/exports explicit
- Test: `tests/unit/test_sacrifice_detector.py`
- Test: `tests/unit/test_exchange_sacrifice.py`

**Interfaces:**

- Consumes: `BoardService.exchange_lines`, `PositionHistory`, `MaterialValues`, and v2 sacrifice thresholds.
- Produces: `detect_exchange_aware_sacrifice(board, initial_fen, moves_uci, candidate_move, material_values, thresholds) -> SacrificeEvidence`.

- [ ] **Step 1: Add regression tests before implementation.**

```python
def test_bxc6_bxc6_is_a_clean_equal_exchange_not_a_sacrifice(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        REGRESSION_FEN,
        (),
        "b5c6",
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )
    assert evidence.detected is False
    assert evidence.exchange is not None
    assert evidence.exchange.clean_trade is True
    assert evidence.exchange.obvious_recapture is True
    assert evidence.exchange.net_material_concession == pytest.approx(0.1)
    assert evidence.exchange.sequence_uci == ("b5c6", "b7c6")
    assert evidence.exchange.sequence_san == ("Bxc6+", "bxc6")


@pytest.mark.parametrize("fen, move", EQUAL_TRADE_CASES)
def test_equal_rook_and_queen_trades_are_not_sacrifices(board, rules_v2, fen, move):
    evidence = detect_exchange_aware_sacrifice(
        board,
        fen,
        (),
        move,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )
    assert evidence.detected is False
    assert evidence.exchange.disposition in {
        ExchangeDisposition.CLEAN_EQUAL_TRADE,
        ExchangeDisposition.OBVIOUS_RECAPTURE,
    }


def test_rook_for_minor_exchange_can_pass_the_net_concession_threshold(board, rules_v2):
    evidence = detect_exchange_aware_sacrifice(
        board,
        ROOK_FOR_MINOR_FEN,
        (),
        ROOK_CAPTURE_MOVE,
        material_values=rules_v2.material_values,
        thresholds=rules_v2.sacrifice,
    )
    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.EXCHANGE_SACRIFICE
    assert (
        evidence.exchange.net_material_concession >= rules_v2.sacrifice.min_net_material_concession
    )
```

Define these concrete legal fixture constants immediately above the tests:

```python
EQUAL_TRADE_CASES = (
    ("8/8/8/8/8/8/rk6/R5K1 w - - 0 1", "a1a2"),  # Rxa2+ Kxa2
    ("8/8/8/8/8/8/qk6/Q5K1 w - - 0 1", "a1a2"),  # Qxa2+ Kxa2
)
ROOK_FOR_MINOR_FEN = "8/8/8/8/8/8/nk6/R5K1 w - - 0 1"
ROOK_CAPTURE_MOVE = "a1a2"
XRAY_FEN = "7k/8/4p3/3p4/8/8/3Q4/3R2K1 w - - 0 1"
XRAY_CANDIDATE = "d2d5"  # Qxd5 exd5 Rxd5
RECOVERED_OFFER_FEN = "6kr/8/8/7Q/8/8/8/6KR w - - 0 1"
RECOVERED_OFFER_MOVE = "h5h7"  # Qh7 Rxh7 Rxh7
```

Use `XRAY_FEN`/`XRAY_CANDIDATE` for the multi-ply x-ray assertion and
`RECOVERED_OFFER_FEN`/`RECOVERED_OFFER_MOVE` for the temporary-offer assertion.
Keep all FENs in the test file with comments explaining their legal sequence;
do not alter existing fixtures.

Also add explicit fixtures for both bishop-for-knight directions, a capture
plus equal recapture, a compensated non-exchange piece offer, and an obvious
recapture. Assert that each rejected case keeps complete exchange evidence and
reason codes. The compensated case passes only after the configured
net-concession and compensation/soundness evidence; the detector alone must
not turn an unsound offer into a sacrifice.

- [ ] **Step 2: Run the new detector tests and verify RED.**

Run: `uv run pytest tests/unit/test_sacrifice_detector.py tests/unit/test_exchange_sacrifice.py -q`

Expected: failure because the v2 evaluator and exchange fields are absent.

- [ ] **Step 3: Implement the pure exchange arithmetic at the application boundary.**

Normalize the candidate through the board port, request typed traces, and
compute material balances from snapshots using `material_balance`. For each
line calculate candidate capture value, mover losses, later captures, final
balance, `net_material_concession=max(0, losses - all_opponent_captures)`,
clean-trade tolerance, immediate/obvious recapture, and recovery. Pick the
defender-best line by greatest net concession, then shortest acceptance line,
then lexicographic UCI sequence.

Return a `SacrificeEvidence` object even when the disposition rejects the
candidate. Set `detected=True` and `kind` only for a genuine destination offer,
left-hanging offer, exchange sacrifice, declined recapture, or
clearance/deflection whose net concession meets the threshold. Add reason
codes for clean, favorable, obvious, recovered, net-threshold, and x-ray
observations. If history is unavailable, do not infer `DECLINED_RECAPTURE`.

- [ ] **Step 4: Run detector tests and the existing v1 detector suite.**

Run: `uv run pytest tests/unit/test_sacrifice_detector.py tests/unit/test_exchange_sacrifice.py tests/unit/test_sacrifice.py -q`

Expected: PASS with v1 behavior unchanged and all v2 exchange regressions covered.

### Task 4: Add v2 shallow surprise evidence and selection path

**Files:**

- Modify: `src/brilliant_chess/application/choose_brilliant_move.py`
- Test: `tests/unit/test_choose_brilliant_move.py`
- Test: `tests/unit/test_non_obviousness.py`

**Interfaces:**

- Consumes: `ExchangeEvidence`, `NonObviousnessThresholds`, `ChessEngine`, and fixed `AnalysisBudget`s.
- Produces: v2 `CandidateAudit` fields for exchange, non-obviousness, detector version, engine identity, and budgets.

- [ ] **Step 1: Write failing selector tests.**

Add scripted-engine tests for these exact outcomes:

```python
def test_v2_rejects_bxc6_even_when_the_candidate_is_engine_best(rules_v2):
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("clean_exchange"),
        board,
        PositionHistory(REGRESSION_FEN),
        rules_v2,
        v2_budget(),
    )
    audit = next(item for item in choice.candidates if item.candidate.move_uci == "b5c6")
    assert audit.decision.selectable is False
    assert audit.decision.rule_set_version == "strict_v2"
    assert any(
        g.gate_id is GateId.SACRIFICE and g.status is GateStatus.FAILED
        for g in audit.decision.gates
    )
    assert audit.exchange is not None


def test_v2_rejects_move_already_obvious_in_shallow_search(rules_v2):
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("shallow_obvious"),
        board,
        PositionHistory(SURPRISE_FEN),
        rules_v2,
        v2_budget(),
    )
    audit = choice.candidates[0]
    assert audit.non_obviousness is not None
    assert audit.non_obviousness.passed is False
    assert audit.decision.selectable is False


def test_v2_accepts_sound_move_that_improves_only_after_deeper_search(rules_v2):
    choice = choose_brilliant_move(
        scripted_engine_for_v2_case("deep_surprise"),
        board,
        PositionHistory(SURPRISE_FEN),
        rules_v2,
        v2_budget(),
    )
    assert choice.move is not None
    assert choice.selected is not None
    assert choice.selected.non_obviousness.condition is NonObviousnessCondition.EP_IMPROVEMENT
```

Define `SURPRISE_FEN` as the existing legal left-hanging-rook fixture
`r2qkb1r/1p3p1p/5np1/3Ppb2/7Q/p1N2N2/PP2PPPP/1RB1KB1R w Kkq - 2 14`; the
scripted candidate for both surprise cases is `e2e3`. This keeps the
non-obviousness tests focused on shallow/deep ranking while the exchange
detector exercises a genuine non-destination offer.

Use fixed scripted responses keyed by FEN, root move, and node budget. Include
one candidate with high score but a failed mandatory gate and assert it is not
selected. Define `v2_budget()` in the test module with
`shallow=AnalysisBudget(nodes=5_000)` and `shallow_multipv=5`. Define
`scripted_engine_for_v2_case(case)` in the same module using the existing
`ScriptedEngine`/`ScriptKey` helpers: its `shallow_obvious` case puts the
candidate at rank 1 with EP improvement below 0.03, while its `deep_surprise`
case puts it outside shallow rank 2 and at confirmed rank 2 with 0.05 EP
improvement. The helper must provide fixed discovery, confirmation,
best-defense, and stability responses for every called budget.

- [ ] **Step 2: Run selector tests and verify RED.**

Run: `uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py -q`

Expected: failure because `StrictSearchBudget` has no shallow stage and the v2
selector does not yet collect exchange/non-obviousness evidence.

- [ ] **Step 3: Implement v2 auditing without changing the v1 path.**

Extend `StrictSearchBudget` with optional `shallow: AnalysisBudget | None` and
`shallow_multipv` defaults after the existing fields so current test
constructors remain valid. For v1, retain the current `_audit_candidate`
behavior and call only the existing destination/left-hanging detector. For
v2, run shallow MultiPV before deep confirmation, record each candidate's
shallow rank and EP, run the exchange-aware detector with `PositionHistory`,
and evaluate the eight gates.

The laboratory's strict default must resolve to `strict_v2`; its v2 budget
uses the configured 5,000-node shallow stage and MultiPV 5. An explicit
`strict_v1` request continues to use the historical budget path.

For a candidate absent from shallow MultiPV, run a fixed-budget root search for
that candidate when it is needed for EP improvement; keep shallow rank as
`None`. `NonObviousnessEvidence` passes when any configured condition passes.
Copy `engine.identity()` and all budget values into `CandidateAudit`. Missing
engine data produces conservative indeterminate/failed evidence, never an
eligible candidate.

Add a selector fixture where the candidate has a high brilliance score but an
unsound best-defense result, and assert it remains unselected. Add separate
fixtures for a shallow rank-one obvious move and a move outside shallow top two
that reaches confirmed top three. The latter must pass the exact configured
surprise condition; no score-only fallback is permitted.

- [ ] **Step 4: Run all selector/domain tests.**

Run: `uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py tests/unit/test_sacrifice_detector.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

Expected: PASS, including historical v1 selector tests and all v2 gate tests.

### Task 5: Version rule-set loading and strict policy audit serialization

**Files:**

- Create: `config/strict_v2.yaml`
- Modify: `src/brilliant_chess/bootstrap/config.py`
- Modify: `src/brilliant_chess/bootstrap/container.py`
- Modify: `src/brilliant_chess/application/play_match.py`
- Modify: `src/brilliant_chess/interfaces/web/schemas.py`
- Modify: `src/brilliant_chess/interfaces/web/routes.py`
- Modify: `src/brilliant_chess/interfaces/web/pgn.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/lab.ts`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_web_api.py`
- Test: `tests/unit/test_match_pgn.py`
- Test: `frontend/src/lib/api.test.ts`

**Interfaces:**

- Consumes: v2 `RuleSet`, `CandidateAudit`, and existing match API structures.
- Produces: `MatchPolicy.STRICT_V2`, `SelectionKind.STRICT_V2`, `Container.rule_set_for(policy)`, and typed v2 audit JSON/PGN.

- [ ] **Step 1: Write failing policy/config/API tests.**

```python
def test_shipped_v2_config_loads_separately():
    settings = load_settings(Path("config/strict_v2.yaml"))
    assert settings.to_rule_set().id == "strict_v2"
    assert settings.to_rule_set().non_obviousness.shallow_nodes == 5_000


def test_container_resolves_both_historical_and_v2_rules():
    container = build_container(Path("config/strict_v1.yaml"))
    assert container.rule_set_for("strict_v1").id == "strict_v1"
    assert container.rule_set_for("strict_v2").id == "strict_v2"


def test_api_accepts_strict_v2_and_reports_its_rule_set(client):
    response = client.post(
        "/api/match",
        json={
            "white": {"strength_key": "maximo", "policy": "strict_v2"},
            "black": {"strength_key": "iniciante", "policy": "normal"},
        },
    )
    assert response.status_code == 201
    assert response.json()["white"]["policy"] == "strict_v2"
```

- [ ] **Step 2: Run the focused tests and verify RED.**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_web_api.py tests/unit/test_match_pgn.py -q`

Expected: failure because the v2 file, policy enum, resolver, and payload fields do not exist.

- [ ] **Step 3: Implement rule-set and wire compatibility.**

Create `config/strict_v2.yaml` by copying the existing objective budgets and
documenting the v2-only sacrifice/non-obviousness fields; do not modify
`config/strict_v1.yaml` thresholds. Add `Settings` conversion for the new
models and make `Container` load the sibling v2 config while preserving
`container.rules` as the configured historical default. `rule_set_for()` must
accept `normal` only as a caller branch and return the requested strict set.

Add `STRICT_V2` to `MatchPolicy` and `SelectionKind`; preserve the existing v1
values. In `routes.step_match`, choose v1 or v2 rules from the container and
call the same normal branch for `normal`. Extend API audit models with exchange
fields (including rejected evidence), non-obviousness measurements, detector
version, engine/NNUE identity, and node budgets. Extend PGN strict comments
with compact v2 provenance while leaving existing v1 comment strings valid.

- [ ] **Step 4: Run backend and frontend contract tests.**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_web_api.py tests/unit/test_match_pgn.py -q`

Run: `npm test -- --run frontend/src/lib/api.test.ts`

Expected: PASS; existing v1 API/PGN assertions remain valid and v2 records are typed.

### Task 6: Document the classifier and prove the complete backend slice

**Files:**

- Modify: `docs/domain-rules.md`
- Modify: `docs/architecture.md`
- Modify: `docs/testing.md`
- Modify: `README.md`
- Create: `docs/decisions/0009-strict-v2-exchange-aware-classifier.md`
- Modify: `tests/unit/test_gates.py` if the gate-count assertion needs v1/v2 separation

- [ ] **Step 1: Write documentation invariant tests before documentation edits.**

```python
def test_v1_gate_shape_is_preserved_and_v2_adds_only_non_obviousness(rules, rules_v2):
    assert [gate.gate_id for gate in evaluate_gates(brilliant_inputs(), rules)] == [
        GateId.LEGAL,
        GateId.QUALITY,
        GateId.SACRIFICE,
        GateId.SOUNDNESS,
        GateId.NOT_BAD_AFTER,
        GateId.NOT_ALREADY_WON,
        GateId.STABILITY,
    ]
    assert GateId.NON_OBVIOUS in {
        gate.gate_id for gate in evaluate_gates(brilliant_inputs(), rules_v2)
    }
```

- [ ] **Step 2: Run the invariant test and confirm its failure or required update.**

Run: `uv run pytest tests/unit/test_gates.py -q`

Expected: the new assertion identifies the exact gate-shape change; fix only
the test helper needed to distinguish v1 from v2.

- [ ] **Step 3: Update permanent records.**

Document v1/v2 identifiers, net-concession semantics, clean-trade rejection,
the Portuguese regression explanation, non-obviousness defaults, provenance
fields, and the explicit non-equivalence to Chess.com. Add ADR 0009 with the
port boundary and compatibility decision. Update architecture/testing/README
usage without removing fair-play or loopback language.

- [ ] **Step 4: Run the full backend quality gate.**

Run: `uv run pytest`

Run: `uv run ruff check .`

Run: `uv run ruff format --check .`

Run: `uv run mypy src`

Run: `uv run pytest -m slow`

Expected: all non-slow tests and quality checks pass; slow tests pass or report
only the existing Stockfish-unavailable skip.
