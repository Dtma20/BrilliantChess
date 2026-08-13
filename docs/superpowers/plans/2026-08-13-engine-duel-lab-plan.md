# Engine Duel Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a local `/laboratorio` page where two independent Stockfish instances play up to 100 full moves, with a selectable `strict_v1` side choosing only fully eligible brilliant moves and otherwise playing its normal best move.

**Architecture:** Keep match lifecycle state in `application/play_match.py`, independently from the human-versus-engine `GameState`. Put strict candidate discovery, confirmation, sacrifice evidence, best-defense and stability evidence in `application/choose_brilliant_move.py`; it consumes existing pure domain gates/scoring and the board/engine ports. The web layer owns volatile match storage, two lazy Stockfish processes, HTTP/PGN serialization, and browser-driven autoplay; no server worker is created.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, python-chess through `PythonChessBoardService`, Stockfish UCI through the existing adapter, vanilla HTML/CSS/JavaScript, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-13-engine-duel-lab-design.md`

## Global Constraints

- Use only the configured Stockfish executable; never expose arbitrary UCI binaries or live-game integration.
- White and Black each use a lazy, independent Stockfish process; divide configured `engine.threads` and `engine.hash_mb` with floors of 1 thread and 16 MB, and close both at FastAPI shutdown.
- `strict_v1` means all seven existing gates pass after discovery, individual confirmation, sacrifice evidence, best-defense and stability work; incomplete evidence is ineligible, never heuristically labelled brilliant.
- A `strict_v1` side selects the eligible candidate with highest score, then lower EP loss, then lexical UCI; no eligible candidate means its own configured-strength normal `play_move` fallback.
- Eligibility analyses run at full Stockfish strength; configured selected strength controls only normal-policy play and strict fallback play.
- Browser `setTimeout` requests one `/step` at a time only while the laboratory page is open; do not add a background server loop, queue, timer, or persistence.
- Cap a match at exactly 200 plies / 100 full moves and finish it as `Empate por limite experimental (100 lances)` with PGN result `1/2-1/2`.
- Preserve loopback defaults and permanent fair-play warnings. This laboratory evaluates only games played on this app's own board.
- Use deterministic node budgets in tests; never use wall-clock budgets in golden or unit tests.
- Do not let `domain/` import FastAPI, Pydantic, subprocess, python-chess, or web modules.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `src/brilliant_chess/application/play_match.py` | Immutable engine-versus-engine state, legal one-ply transition, cap/result behavior, and per-ply audit record. |
| `src/brilliant_chess/application/choose_brilliant_move.py` | Strict selector that creates auditable candidate decisions from existing analysis, detector, gate, and scoring primitives. |
| `src/brilliant_chess/application/sacrifice_detector.py` | Adapter-facing detector for a piece offered on the candidate destination and its legal acceptance captures. |
| `src/brilliant_chess/interfaces/web/engine_pair_session.py` | Two lazy Stockfish clients and deterministic split of process resources. |
| `src/brilliant_chess/interfaces/web/match_store.py` | Thread-safe, bounded, in-memory `MatchState` store. |
| `src/brilliant_chess/interfaces/web/pgn.py` | Adds match PGN headers and policy/selection comments while preserving existing game export. |
| `src/brilliant_chess/interfaces/web/schemas.py` | Request/response DTOs for match state and compact audit data. |
| `src/brilliant_chess/interfaces/web/routes.py` | Match create/read/step/export endpoints and dependency accessors. |
| `src/brilliant_chess/interfaces/web/static/lab.html` | Laboratory controls, fair-play copy, read-only board, move list, and audit panel. |
| `src/brilliant_chess/interfaces/web/static/lab.js` | Fetch/update flow and page-lifetime autoplay timer. |

### Task 1: Add pure match lifecycle and volatile match store

**Files:**
- Create: `src/brilliant_chess/application/play_match.py`
- Create: `src/brilliant_chess/interfaces/web/match_store.py`
- Create: `tests/unit/test_play_match.py`
- Create: `tests/unit/test_match_store.py`

**Interfaces:**
- Consumes: `BoardService`, `GameStatus`, `Color`, `Move`, `strength_by_key`.
- Produces: `MatchPolicy`, `SelectionKind`, `MatchProfile`, `MatchMove`, `MatchState`, `start_match`, `current_view`, `can_step`, `record_move`, `result_text`, and `MatchStore`.
- `record_move(board, state, move, selection, decision) -> MatchState` must validate and normalize the move, append UCI/SAN/audit in lockstep, update `current_fen`, and reject a finished or capped state.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_match_records_one_legal_ply_with_audit(board):
    state = start_match("m1", STARTING_FEN, MatchProfile("maximo", MatchPolicy.STRICT_V1), MatchProfile("iniciante", MatchPolicy.NORMAL), max_plies=200)
    moved = record_move(board, state, Move("e2e4"), SelectionKind.STRICT_V1, decision=None)
    assert moved.moves_uci == ("e2e4",)
    assert moved.moves_san == ("e4",)
    assert moved.current_fen == board.view(STARTING_FEN, ("e2e4",)).position.fen
    assert moved.moves[0].selection is SelectionKind.STRICT_V1

def test_two_hundredth_ply_finishes_as_experimental_draw(board):
    state = replace(start_match("m2", STARTING_FEN, MatchProfile("maximo", MatchPolicy.NORMAL), MatchProfile("iniciante", MatchPolicy.NORMAL), max_plies=2), moves_uci=("e2e4",), moves_san=("e4",), current_fen=board.view(STARTING_FEN, ("e2e4",)).position.fen)
    capped = record_move(board, state, Move("e7e5"), SelectionKind.NORMAL, decision=None)
    assert capped.is_finished(board) is True
    assert result_text(board, capped) == "Empate por limite experimental (100 lances)"
    with pytest.raises(DomainError):
        record_move(board, capped, Move("g1f3"), SelectionKind.NORMAL, decision=None)
```

- [ ] **Step 2: Run the new tests and confirm import failure**

Run: `uv run pytest tests/unit/test_play_match.py tests/unit/test_match_store.py -v`

Expected: FAIL because the match lifecycle and store do not exist.

- [ ] **Step 3: Implement the immutable state and store**

```python
class MatchPolicy(StrEnum):
    NORMAL = "normal"
    STRICT_V1 = "strict_v1"

class SelectionKind(StrEnum):
    NORMAL = "normal"
    STRICT_V1 = "strict_v1"
    FALLBACK = "fallback"

@dataclass(frozen=True)
class MatchProfile:
    strength_key: str
    policy: MatchPolicy

@dataclass(frozen=True)
class MatchMove:
    color: Color
    uci: str
    san: str
    selection: SelectionKind
    decision: BrilliantDecision | None

@dataclass(frozen=True)
class MatchState:
    match_id: str
    initial_fen: str
    current_fen: str
    white: MatchProfile
    black: MatchProfile
    moves_uci: tuple[str, ...] = ()
    moves_san: tuple[str, ...] = ()
    moves: tuple[MatchMove, ...] = ()
    max_plies: int = 200
```

Implement `is_capped` as `len(moves_uci) >= max_plies`; `is_finished(board)` as `is_capped or current_view(board, state).status.is_finished`. Validate both strength keys in `start_match`, enforce `max_plies > 0`, and retain `GameStatus` rather than adding a duplicate domain status enum. Implement `MatchStore` by copying the locking, 64-entry FIFO eviction, `new_id`, `get`, and `save` behavior from `GameStore`, but with `MatchState` and `MAX_MATCHES = 16`.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/unit/test_play_match.py tests/unit/test_match_store.py -v`

Expected: PASS, including invalid strength, store eviction, board-terminal, and cap-terminal cases.

- [ ] **Step 5: Commit the lifecycle slice**

```bash
git add src/brilliant_chess/application/play_match.py src/brilliant_chess/interfaces/web/match_store.py tests/unit/test_play_match.py tests/unit/test_match_store.py
git commit -m "feat: add engine match lifecycle"
```

### Task 2: Implement destination-offer evidence and the strict selector

**Files:**
- Create: `src/brilliant_chess/application/sacrifice_detector.py`
- Create: `src/brilliant_chess/application/choose_brilliant_move.py`
- Create: `tests/unit/test_sacrifice_detector.py`
- Create: `tests/unit/test_choose_brilliant_move.py`

**Interfaces:**
- Consumes: `ChessEngine`, `BoardService`, `RuleSet`, `AnalysisRequest`, `GateInputs`, `ScoringInputs`, `evaluate_gates`, and `decide`.
- Produces: `StrictSearchBudget`, `CandidateAudit`, `BrilliantMoveChoice`, `detect_destination_offer`, and `choose_brilliant_move`.
- `choose_brilliant_move(engine, board, position, rules, budget) -> BrilliantMoveChoice` returns `move=None` when nothing is eligible and includes every confirmed candidate's audit.

- [ ] **Step 1: Write focused failing tests for detector and selection**

```python
def test_destination_detector_requires_a_non_pawn_piece_capturable_on_its_square(board):
    evidence = detect_destination_offer(board, Position.from_fen(OFFER_FEN), Move("h2h7"), rules)
    assert evidence.detected is True
    assert evidence.kind is SacrificeKind.DESTINATION_OFFER
    assert evidence.offered_piece_square == "h7"
    assert evidence.signals.legal_capture_available is True

def test_selector_returns_only_a_candidate_with_all_seven_passed_gates(board, scripted_engine, rules):
    choice = choose_brilliant_move(scripted_engine, board, Position.from_fen(OFFER_FEN), rules, TEST_BUDGET)
    assert choice.move == Move("h2h7")
    assert choice.selected.audit.decision.is_brilliant is True
    assert all(gate.passed for gate in choice.selected.audit.decision.gates)

def test_selector_breaks_score_tie_by_ep_loss_then_uci(board, scripted_engine, rules):
    choice = choose_brilliant_move(scripted_engine, board, Position.from_fen(TIE_FEN), rules, TEST_BUDGET)
    assert choice.move.uci == "a1a2"

def test_missing_best_defense_or_stability_evidence_is_not_selectable(board, scripted_engine, rules):
    choice = choose_brilliant_move(scripted_engine, board, Position.from_fen(OFFER_FEN), rules, TEST_BUDGET)
    assert choice.move is None
    assert GateStatus.INDETERMINATE in {g.status for g in choice.candidates[0].audit.decision.gates}
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/unit/test_sacrifice_detector.py tests/unit/test_choose_brilliant_move.py -v`

Expected: FAIL because the detector, strict budgets, and selector are not defined.

- [ ] **Step 3: Implement conservative structural evidence and selection orchestration**

```python
@dataclass(frozen=True)
class StrictSearchBudget:
    discovery: AnalysisBudget
    confirmation: AnalysisBudget
    best_defense: AnalysisBudget
    stability: AnalysisBudget
    multipv: int
    max_candidates: int

@dataclass(frozen=True)
class CandidateAudit:
    candidate: Candidate
    decision: BrilliantDecision
    best_defense_uci: str | None
    stability_depth: int | None

@dataclass(frozen=True)
class BrilliantMoveChoice:
    move: Move | None
    selected: CandidateAudit | None
    candidates: tuple[CandidateAudit, ...]
```

`detect_destination_offer` must: normalize the candidate; inspect the resulting `BoardView.snapshot.placement`; reject a pawn/king/no piece on the destination; find opponent legal moves whose target square is that destination; and return `NO_SACRIFICE` when none exist. For an offer, record the legal accepting UCIs, nominal material value, and `legal_capture_available=True`; derive confidence through the existing `sacrifice_confidence`/`reasons_for` functions only. Do not claim `material_deficit_in_acceptance`, `engine_considers_acceptance`, `tactical_mechanism_in_pv`, or persistence until the selector measures them.

`choose_brilliant_move` must call `analyze_position` with the discovery/confirmation budgets. For every confirmed candidate, it must: (1) call the detector; (2) analyze the candidate position at `best_defense` and flip the opponent's EP to the candidate mover's POV; (3) use the actual best reply to determine whether the candidate PV requires a different opponent reply; (4) rerun that root candidate at `stability`; (5) calculate EP drift and PV overlap; (6) complete sacrifice signals only from measured acceptance/PV/stability facts; (7) construct `GateInputs` and `ScoringInputs`, then call `evaluate_gates` and `decide`. A missing engine response makes the associated gate indeterminate/conservative rather than guessed. Sort only `decision.selectable` audits by `(-decision.score, candidate.expected_points_loss, candidate.move_uci)`.

- [ ] **Step 4: Run the selector and existing domain tests**

Run: `uv run pytest tests/unit/test_sacrifice_detector.py tests/unit/test_choose_brilliant_move.py tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -v`

Expected: PASS. The test data must cover no offered piece, capturable pawn, accepted non-pawn offer, a rejected gate, missing evidence, and deterministic tie order.

- [ ] **Step 5: Commit the strict-selection slice**

```bash
git add src/brilliant_chess/application/sacrifice_detector.py src/brilliant_chess/application/choose_brilliant_move.py tests/unit/test_sacrifice_detector.py tests/unit/test_choose_brilliant_move.py
git commit -m "feat: select strict brilliant engine moves"
```

### Task 3: Add laboratory configuration and independent engine-pair lifecycle

**Files:**
- Create: `src/brilliant_chess/interfaces/web/engine_pair_session.py`
- Modify: `src/brilliant_chess/bootstrap/config.py`
- Modify: `config/strict_v1.yaml`
- Modify: `src/brilliant_chess/interfaces/web/app.py`
- Create: `tests/unit/test_engine_pair_session.py`
- Modify: `tests/unit/test_config.py`
- Modify: `tests/unit/test_web_api.py`

**Interfaces:**
- Consumes: `Settings`, `StockfishEngine`, engine path resolution, and `StrictSearchBudget`.
- Produces: `LabModel`, `EnginePairSession.white_engine()`, `EnginePairSession.black_engine()`, `EnginePairSession.close()`, and `LabModel.strict_budget()`.

- [ ] **Step 1: Write failing configuration and session tests**

```python
def test_lab_config_uses_fixed_node_budgets():
    lab = Settings().web.lab
    assert lab.max_fullmoves == 100
    assert lab.strict_budget().discovery.nodes == 80_000
    assert lab.strict_budget().stability.nodes == 400_000

def test_pair_session_creates_two_engines_with_split_resources(settings, monkeypatch):
    pair = EnginePairSession(settings)
    assert pair.white_engine() is not pair.black_engine()
    assert captured_options == [(3, 512), (3, 512)]
    pair.close()
    assert all(engine.closed for engine in created)
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_engine_pair_session.py -v`

Expected: FAIL because `web.lab` and `EnginePairSession` do not exist.

- [ ] **Step 3: Add validated defaults and pair ownership**

```python
class LabModel(_Strict):
    max_fullmoves: int = Field(default=100, ge=1, le=100)
    autoplay_delay_ms: int = Field(default=250, ge=50, le=10_000)
    strict_multipv: int = Field(default=6, ge=1, le=16)
    strict_candidates: int = Field(default=6, ge=1, le=16)
    strict_discovery_nodes: int = Field(default=80_000, gt=0)
    strict_confirmation_nodes: int = Field(default=200_000, gt=0)
    strict_best_defense_nodes: int = Field(default=200_000, gt=0)
    strict_stability_nodes: int = Field(default=400_000, gt=0)

class WebModel(_Strict):
    lab: LabModel = LabModel()
```

Add the same values under `web.lab` in YAML. `strict_budget()` creates four `AnalysisBudget(nodes=...)` values and sets `max_candidates` to no more than `strict_multipv`. `EnginePairSession` must create each `StockfishEngine` lazily with the same resolved binary path, `threads=max(1, settings.engine.threads // 2)`, `hash_mb=max(16, settings.engine.hash_mb // 2)`, and existing timeout. Protect creation with a lock and make `close()` idempotently close both created engines. Add `app.state.matches` and `app.state.engine_pair_session`; close the old single session and the pair session in lifespan, even when one close raises.

- [ ] **Step 4: Run focused lifecycle tests**

Run: `uv run pytest tests/unit/test_config.py tests/unit/test_engine_pair_session.py tests/unit/test_web_api.py::test_engine_is_closed_on_shutdown -v`

Expected: PASS, including odd resource values (`threads=1`, `hash_mb=16`) and shutdown of two fake engines.

- [ ] **Step 5: Commit configuration and engine ownership**

```bash
git add src/brilliant_chess/bootstrap/config.py config/strict_v1.yaml src/brilliant_chess/interfaces/web/engine_pair_session.py src/brilliant_chess/interfaces/web/app.py tests/unit/test_config.py tests/unit/test_engine_pair_session.py tests/unit/test_web_api.py
git commit -m "feat: add paired Stockfish laboratory session"
```

### Task 4: Expose match HTTP APIs and strict fallback behavior

**Files:**
- Modify: `src/brilliant_chess/interfaces/web/schemas.py`
- Modify: `src/brilliant_chess/interfaces/web/routes.py`
- Modify: `tests/fakes/stub_engine.py`
- Modify: `tests/unit/test_web_api.py`

**Interfaces:**
- Consumes: `MatchState`, `MatchStore`, `EnginePairSession`, `choose_brilliant_move`, `LabModel.strict_budget()`.
- Produces: `POST /api/match`, `GET /api/match/{match_id}`, `POST /api/match/{match_id}/step`, and API models `NewMatchIn`, `MatchOut`, `MatchMoveOut`, `CandidateAuditOut`.
- `POST /step` uses the engine selected by `view.position.side_to_move`, uses its profile policy, and saves exactly one ply.

- [ ] **Step 1: Write failing API tests using a fake pair**

```python
def test_create_read_and_step_match(client):
    created = client.post("/api/match", json={"white": {"strength_key": "maximo", "policy": "strict_v1"}, "black": {"strength_key": "iniciante", "policy": "normal"}}).json()
    stepped = client.post(f"/api/match/{created['match_id']}/step").json()
    assert len(stepped["moves_uci"]) == 1
    assert stepped["moves"][0]["color"] == "white"
    assert client.get(f"/api/match/{created['match_id']}").json()["match_id"] == created["match_id"]

def test_strict_side_falls_back_to_its_configured_strength(client, monkeypatch):
    monkeypatch.setattr(routes, "choose_brilliant_move", lambda *args: BrilliantMoveChoice(None, None, ()))
    match = create_strict_white_match(client)
    result = client.post(f"/api/match/{match['match_id']}/step").json()
    assert result["moves"][0]["selection"] == "fallback"
    assert client.app.state.engine_pair_session.white.calls[0][1] == "maximo"

def test_capped_match_refuses_one_more_step(client):
    match = create_match_with_max_plies(client, max_plies=1)
    client.post(f"/api/match/{match['match_id']}/step")
    assert client.post(f"/api/match/{match['match_id']}/step").status_code == 400
```

- [ ] **Step 2: Run the API tests and confirm failure**

Run: `uv run pytest tests/unit/test_web_api.py -v`

Expected: FAIL because match routes and pair-session fakes are absent.

- [ ] **Step 3: Implement DTOs, dependencies, and one-ply route**

```python
class MatchProfileIn(_Model):
    strength_key: str = "clube"
    policy: MatchPolicy = MatchPolicy.NORMAL

class NewMatchIn(_Model):
    white: MatchProfileIn = MatchProfileIn(strength_key="maximo", policy=MatchPolicy.STRICT_V1)
    black: MatchProfileIn = MatchProfileIn(strength_key="iniciante", policy=MatchPolicy.NORMAL)
    initial_fen: str | None = None

@router.post("/match/{match_id}/step")
def step_match(match_id: str, request: Request, board: BoardDep, store: MatchStoreDep, pair: PairSessionDep) -> MatchOut:
    state = store.get(match_id)
    view = play_match.current_view(board, state)
    profile, engine = _profile_and_engine(state, view.position.side_to_move, pair)
    rules = request.app.state.container.rules
    lab = request.app.state.container.settings.web.lab
    choice = choose_brilliant_move(engine, board, view.position, rules, lab.strict_budget()) if profile.policy is MatchPolicy.STRICT_V1 else None
    move = choice.move if choice and choice.move else engine.play_move(view.position, strength_by_key(profile.strength_key))
    selection = SelectionKind.STRICT_V1 if choice and choice.move else (SelectionKind.FALLBACK if profile.policy is MatchPolicy.STRICT_V1 else SelectionKind.NORMAL)
    return match_out(board, store.save(record_move(board, state, move, selection, choice.selected.decision if choice and choice.selected else None)))

def _profile_and_engine(state: MatchState, color: Color, pair: EnginePairSession) -> tuple[MatchProfile, ChessEngine]:
    return (state.white, pair.white_engine()) if color is Color.WHITE else (state.black, pair.black_engine())
```

`MatchOut` must include board, both resolved strength labels/policies, `moves_uci`, `moves_san`, `moves`, `result_text`, `can_step`, and compact audit fields: selected UCI/SAN, score, rule-set version, gate ID/status/measured/threshold/explanation, reason codes, and fallback indication. The fake pair must expose named `white`/`black` `StubEngine` instances and close both. Route errors reuse `translated_errors`; an unknown match and any finished/capped step return 400.

- [ ] **Step 4: Run match and regression API tests**

Run: `uv run pytest tests/unit/test_web_api.py -v`

Expected: PASS for normal black/white turns, strict selection, strict fallback, unknown match, terminal game, maximum plies, and all existing `/game`/analysis routes.

- [ ] **Step 5: Commit the API slice**

```bash
git add src/brilliant_chess/interfaces/web/schemas.py src/brilliant_chess/interfaces/web/routes.py tests/fakes/stub_engine.py tests/unit/test_web_api.py
git commit -m "feat: add engine duel match API"
```

### Task 5: Export auditable laboratory PGN

**Files:**
- Modify: `src/brilliant_chess/interfaces/web/pgn.py`
- Modify: `src/brilliant_chess/interfaces/web/routes.py`
- Create: `tests/unit/test_match_pgn.py`
- Modify: `tests/unit/test_web_api.py`

**Interfaces:**
- Consumes: `MatchState`, `MatchMove`, `BoardView`, and `STARTING_FEN`.
- Produces: `build_match_pgn(state, initial, current, standard_fen) -> str` and `GET /api/match/{match_id}/pgn`.

- [ ] **Step 1: Write failing PGN tests**

```python
def test_match_pgn_identifies_profiles_and_selection_comments(board):
    text = build_match_pgn(state_with_strict_and_fallback_moves, initial, current, standard_fen=STARTING_FEN)
    assert '[White "Stockfish (Máximo, strict_v1)"]' in text
    assert '[Black "Stockfish (Iniciante, normal)"]' in text
    assert "{policy=strict_v1 selection=strict_v1 score=87.50}" in text
    assert "{policy=strict_v1 selection=fallback reason=no_eligible_candidate}" in text

def test_cap_uses_draw_result_and_experimental_comment(board):
    text = build_match_pgn(capped_state, initial, current, standard_fen=STARTING_FEN)
    assert '[Result "1/2-1/2"]' in text
    assert "{result=experimental_move_limit fullmoves=100}" in text
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `uv run pytest tests/unit/test_match_pgn.py tests/unit/test_web_api.py::test_match_pgn_download -v`

Expected: FAIL because match PGN export does not exist.

- [ ] **Step 3: Implement match serialization without changing existing game PGN semantics**

```python
def build_match_pgn(state: MatchState, initial: BoardView, current: BoardView, *, standard_fen: str) -> str:
    result = "1/2-1/2" if state.is_capped else _result(current.status, current.position.side_to_move)
    headers = [("Event", "Brilliant Chess - Laboratório de motores"), ("Site", "Localhost"), ("White", _match_player_name(state.white)), ("Black", _match_player_name(state.black)), ("Result", result)]
    tokens = _movetext_with_comments(state.moves, initial.snapshot.fullmove_number, initial.position.side_to_move, result)
    return _headers(headers) + "\n" + tokens + "\n"
```

Use the existing escaping and custom-FEN header behavior. Add one comment immediately after each SAN token: normal policy is `{policy=normal selection=normal}`, selected strict includes score/rule set, and fallback includes `reason=no_eligible_candidate`. Append the cap comment before the final result token. Return the attachment as `brilliant-chess-match-{match_id}.pgn` with the same chess-PGN media type.

- [ ] **Step 4: Run PGN tests and prior game-export tests**

Run: `uv run pytest tests/unit/test_match_pgn.py tests/unit/test_web_api.py -v`

Expected: PASS, including checkmate, custom FEN, unfinished match, capped match, and unknown match response.

- [ ] **Step 5: Commit PGN export**

```bash
git add src/brilliant_chess/interfaces/web/pgn.py src/brilliant_chess/interfaces/web/routes.py tests/unit/test_match_pgn.py tests/unit/test_web_api.py
git commit -m "feat: export engine duel PGN"
```

### Task 6: Build the local laboratory interface and browser-lifetime autoplay

**Files:**
- Create: `src/brilliant_chess/interfaces/web/static/lab.html`
- Create: `src/brilliant_chess/interfaces/web/static/lab.js`
- Modify: `src/brilliant_chess/interfaces/web/static/api.js`
- Modify: `src/brilliant_chess/interfaces/web/static/index.html`
- Modify: `src/brilliant_chess/interfaces/web/static/play.html`
- Modify: `src/brilliant_chess/interfaces/web/static/analysis.html`
- Modify: `src/brilliant_chess/interfaces/web/static/app.css`
- Modify: `src/brilliant_chess/interfaces/web/app.py`
- Create: `tests/unit/test_lab_static.py`

**Interfaces:**
- Consumes: `/api/strengths`, `/api/match`, `/api/match/{id}`, `/step`, `/pgn`, existing `ChessBoard` from `board.js`.
- Produces: `/laboratorio`, `createMatch`, `readMatch`, `stepMatch`, `matchPgnUrl`, and an autoplay loop that has no side effect after `pagehide`.

- [ ] **Step 1: Write failing static/page tests**

```python
def test_laboratory_page_and_api_helpers_are_exposed(client):
    page = client.get("/laboratorio")
    assert page.status_code == 200
    assert 'id="start-match"' in page.text
    script = client.get("/static/lab.js").text
    assert "setTimeout" in script
    assert "pagehide" in script
    assert "stepMatch" in client.get("/static/api.js").text
```

- [ ] **Step 2: Run the test and confirm failure**

Run: `uv run pytest tests/unit/test_lab_static.py -v`

Expected: FAIL because the laboratory page and JavaScript files are absent.

- [ ] **Step 3: Implement readable controls and one-request autoplay**

```javascript
let matchId = null;
let autoplay = false;
let timerId = null;
let stepping = false;

async function scheduleNext() {
  if (!autoplay || !matchId || stepping || state?.can_step !== true) return;
  timerId = window.setTimeout(async () => {
    stepping = true;
    try { render(await stepMatch(matchId)); }
    finally { stepping = false; scheduleNext(); }
  }, AUTOPLAY_DELAY_MS);
}

window.addEventListener("pagehide", () => {
  autoplay = false;
  window.clearTimeout(timerId);
});
```

Render two color-specific profile selectors populated from `/api/strengths`, a policy selector (`normal`/`strict_v1`) per side, start, pause/resume, restart, and PGN download actions. Make the board display-only: do not attach move callbacks. Render current side, configured policy and strength, SAN history with `strict`/`fallback`/`normal` tags, terminal result, and a collapsible audit panel with score, gates, measurements, threshold, explanations, and fallback reason. Include the existing fair-play statement on this page and add `Laboratório` to every page navigation. Add a `/laboratorio` `FileResponse` route.

- [ ] **Step 4: Run static/page tests and a browser-independent regression check**

Run: `uv run pytest tests/unit/test_lab_static.py tests/unit/test_web_api.py -v`

Expected: PASS. Inspect the served HTML manually to confirm it states that it evaluates only the local board and that pausing clears the pending timer.

- [ ] **Step 5: Commit the web interface**

```bash
git add src/brilliant_chess/interfaces/web/static/lab.html src/brilliant_chess/interfaces/web/static/lab.js src/brilliant_chess/interfaces/web/static/api.js src/brilliant_chess/interfaces/web/static/index.html src/brilliant_chess/interfaces/web/static/play.html src/brilliant_chess/interfaces/web/static/analysis.html src/brilliant_chess/interfaces/web/static/app.css src/brilliant_chess/interfaces/web/app.py tests/unit/test_lab_static.py
git commit -m "feat: add engine duel laboratory UI"
```

### Task 7: Document strict laboratory semantics and verify the complete delivery

**Files:**
- Modify: `docs/domain-rules.md`
- Modify: `config/strict_v1.yaml`
- Create: `docs/decisions/0006-engine-duel-laboratory.md`
- Modify: `README.md`
- Modify: `docs/testing.md`
- Modify: `tests/unit/test_gates.py`

**Interfaces:**
- Consumes: final strict selector, config, routes, PGN format, and existing fair-play guidance.
- Produces: documented `strict_v1` laboratory contract, node-budget provenance, reproducible local test commands, and an ADR explaining independent engines/browser-driven execution.

- [ ] **Step 1: Write a failing documentation-invariant test**

```python
def test_all_gates_are_required_for_strict_selection(rules, complete_inputs):
    gates = evaluate_gates(complete_inputs, rules)
    assert all_gates_passed(gates) is True
    rejected = replace(complete_inputs, expected_points_loss_after_best_defense=None)
    assert all_gates_passed(evaluate_gates(rejected, rules)) is False
```

- [ ] **Step 2: Run the test and confirm the added invariant is exercised**

Run: `uv run pytest tests/unit/test_gates.py -v`

Expected: PASS after the selector semantics are covered; if it fails, correct the test fixture or gate implementation before documentation.

- [ ] **Step 3: Update permanent project records**

Document in `docs/domain-rules.md`: the `strict_v1` selector pipeline, every gate remains mandatory, no-evidence behavior, tiebreak order, normal fallback, and no equivalence to Chess.com labels. Keep the exact `web.lab` defaults in `config/strict_v1.yaml` aligned with `LabModel`. ADR 0006 records two independent processes, full-strength eligibility analysis, selected-strength fallback, volatile server state, browser-only autoplay, 100-full-move cap, and local-only fair play. README adds the `/laboratorio` workflow and the port-conflict remedy (`8000` already occupied: stop the prior server or set `web.port` to another local port). `docs/testing.md` adds fake-pair API tests and optional real Stockfish slow-test guidance.

- [ ] **Step 4: Run full quality gates**

Run: `uv run pytest`

Expected: PASS.

Run: `uv run ruff check .; uv run ruff format --check .; uv run mypy src`

Expected: all commands exit 0.

Run: `uv run brilliant-chess doctor`

Expected: reports the configured local Stockfish setup or its existing actionable installation diagnostic.

- [ ] **Step 5: Commit docs and verified delivery**

```bash
git add docs/domain-rules.md config/strict_v1.yaml docs/decisions/0006-engine-duel-laboratory.md README.md docs/testing.md tests/unit/test_gates.py
git commit -m "docs: document engine duel laboratory"
```

## Plan self-review

- Spec coverage: Tasks 1 and 4 provide separate match state and a one-ply API; Task 2 enforces faithful `strict_v1`, sacrifice evidence, full gate audit, tiebreak, and fallback boundary; Task 3 provides same-binary independent engine processes and deterministic budgets; Task 5 records reproducible PGN; Task 6 makes the browser own autoplay and provides the prescribed UI; Task 7 records rules, ADR, fair-play, port remediation, and quality gates.
- Placeholder scan: no unspecified implementation items remain; exact files, types, defaults, commands, expected outcomes, and selection behavior are stated per task.
- Type consistency: `MatchState` is produced by Task 1, used by Tasks 4–5; `CandidateAudit` and `BrilliantMoveChoice` are produced by Task 2 and stored/rendered by Tasks 1, 4–6; `LabModel.strict_budget()` is produced by Task 3 and consumed by Task 4.
