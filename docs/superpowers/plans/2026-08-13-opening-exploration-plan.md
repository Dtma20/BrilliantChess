# Laboratory Opening Exploration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add deterministic, locally executed opening exploration with seeded replay, session novelty, four quality modes, typed move audits, API/PGN metadata, and a preserved laboratory layout.

**Architecture:** Keep opening selection separate from side policy selection. Parse a small project-authored YAML suite in an adapter, use a pure seeded selector plus a locked in-memory session usage tracker, and store the selected phase/audits in `MatchState`. The step route handles opening moves first and then delegates unchanged to `normal`, `strict_v1`, or `strict_v2`.

**Tech Stack:** Python 3.12, dataclasses and `StrEnum`, `random.Random` plus `secrets` only at the web/application boundary, YAML bootstrap validation, FastAPI/Pydantic schema version 3, PGN text export, React/Vite/TypeScript/Vitest.

**Spec:** `docs/superpowers/specs/2026-08-13-opening-exploration-design.md`

## Global Constraints

- Opening exploration is local and offline; no live-game integration, browser automation, scraping, overlay, or external request is permitted.
- Every opening move is legal, typed, and auditable; opening moves never receive a brilliant/near-brilliant/fallback/normal label.
- Generated randomness is seeded and node-budgeted; tests never depend on wall-clock timing or uncontrolled entropy.
- `strict_v1`, `strict_v2`, and `normal` thresholds remain unchanged after the opening phase.
- The laboratory's full-width primary button and four-button secondary row remain intact.
- Existing uncommitted PGN/FEN and laboratory UI edits are preserved; modify only the smallest surrounding regions.
- Do not add a large binary opening book or engine binary.

### Task 1: Add opening domain models, validated modes, and the offline suite

**Files:**

- Create: `src/brilliant_chess/domain/opening.py`
- Modify: `src/brilliant_chess/domain/values.py`
- Modify: `src/brilliant_chess/bootstrap/config.py`
- Create: `data/openings/suite_v1.yaml`
- Create: `data/openings/README.md`
- Test: `tests/unit/test_opening_models.py`
- Test: `tests/unit/test_config.py`

**Interfaces:**

- Consumes: `Move`, `Position`, `AnalysisBudget`, existing Pydantic/YAML bootstrap conventions.
- Produces: `OpeningMode`, `OpeningConfig`, `OpeningLine`, `OpeningIdentity`, `OpeningPhaseState`, `OpeningExitReason`, `OpeningMoveAudit`, and `OpeningModeModel`/`OpeningConfigModel`.

- [ ] **Step 1: Write failing model/config tests.**

```python
def test_opening_modes_and_default_are_typed():
    settings = Settings()
    assert settings.web.lab.opening.default_mode is OpeningMode.EXPLORATORY
    assert settings.web.lab.opening.for_mode(OpeningMode.EXPLORATORY).multipv == 6
    assert settings.web.lab.opening.for_mode(OpeningMode.EXPLORATORY).max_ep_loss == pytest.approx(
        0.08
    )


def test_opening_line_requires_nonempty_legal_sequence_shape():
    line = OpeningLine(
        line_id="e4-italian",
        family="e4",
        eco="C50",
        name="Italian Game",
        variation="Giuoco Piano",
        moves_uci=("e2e4", "e7e5"),
        weight=1.0,
    )
    assert line.moves_uci[0] == "e2e4"


def test_chaotic_mode_is_experimental():
    assert Settings().web.lab.opening.for_mode(OpeningMode.CHAOTIC).experimental is True
```

- [ ] **Step 2: Run the tests and verify RED.**

Run: `uv run pytest tests/unit/test_opening_models.py tests/unit/test_config.py -q`

Expected: failure because opening models and config fields do not exist.

- [ ] **Step 3: Implement the typed configuration and dataset.**

Add `OpeningMode` values `off`, `controlled`, `exploratory`, and `chaotic`.
Define immutable `OpeningLine`, `OpeningIdentity`, `OpeningConfig`,
`OpeningPhaseState`, and `OpeningMoveAudit`. `OpeningConfig` carries mode,
optional seed, exit full-move bounds, MultiPV, max EP loss, temperature,
additional sampled plies, and a node budget. `OpeningPhaseState` carries
active/ended state, planned exit ply, completed opening plies, selected line,
and an explicit exit reason.

Under `web.lab.opening`, validate these defaults:

```yaml
controlled: {min_fullmove: 6, max_fullmove: 10, multipv: 4, max_ep_loss: 0.02, temperature: 0.01, extra_plies: 0}
exploratory: {min_fullmove: 4, max_fullmove: 10, multipv: 6, max_ep_loss: 0.08, temperature: 0.04, extra_plies: 3}
chaotic: {min_fullmove: 2, max_fullmove: 8, multipv: 8, max_ep_loss: 0.18, temperature: 0.10, extra_plies: 4, experimental: true}
```

Use a node field for the opening search budget. Include `off` as a valid mode
with no line selection. Add at least 16 concise project-authored lines across
the requested first-move families, with ECO/name/variation and legal UCI
sequences. `data/openings/README.md` states the project-authored provenance,
GPLv3-compatible terms, dataset version, and no-network rule.

Each shipped line extends beyond the largest configured exit point (including
the extra sampled plies) so a normal starting-position match can reach its
planned exit without inventing book moves. The selector records the actual
planned ply when a custom FEN or a shorter fixture forces an earlier end.

The suite explicitly covers 1.e4, 1.d4, 1.c4, 1.Nf3, flank moves, and gambit
families; each entry has a stable id and a reviewable UCI sequence.

- [ ] **Step 4: Run focused model/config tests.**

Run: `uv run pytest tests/unit/test_opening_models.py tests/unit/test_config.py -q`

Expected: PASS, including strict validation of ranges and the exploratory default.

### Task 2: Parse and select openings deterministically

**Files:**

- Create: `src/brilliant_chess/adapters/openings/__init__.py`
- Create: `src/brilliant_chess/adapters/openings/suite.py`
- Create: `src/brilliant_chess/application/opening_exploration.py`
- Create: `src/brilliant_chess/interfaces/web/opening_session.py`
- Test: `tests/unit/test_opening_suite.py`
- Test: `tests/unit/test_opening_exploration.py`

**Interfaces:**

- Consumes: YAML suite, `BoardService`, `OpeningConfig`, injectable `random.Random`, and immutable usage snapshots.
- Produces: `load_opening_suite(path)`, `OpeningSelector.choose()`, `OpeningSelector.sample_move()`, and a locked session usage service.

- [ ] **Step 1: Write failing deterministic selector tests.**

Add a fixture that constructs `OpeningSelector` from two project-authored
lines, a `PythonChessBoardService`, and `OpeningConfig(mode=EXPLORATORY,
seed=42)`. The fixture's first line is `e2e4 e7e5 g1f3`, the second is
`d2d4 d7d5 c2c4`, and both have weight 1.0. The fixture overrides the exit
range to full move 1 so the short lines are sufficient. Add an
`OpeningConfig.with_seed` test helper that returns a copy with the requested
seed.

```python
def test_same_seed_reproduces_line_exit_and_sampled_moves(selector, config):
    first = selector.choose(STARTING_FEN, config.with_seed(42))
    second = selector.choose(STARTING_FEN, config.with_seed(42))
    assert first.identity == second.identity
    assert first.planned_exit_ply == second.planned_exit_ply


def test_fixed_different_seeds_produce_multiple_sequences(selector, config):
    sequences = {
        selector.choose(STARTING_FEN, config.with_seed(seed)).identity.line_id
        for seed in (2, 3, 5, 7, 11, 13)
    }
    assert len(sequences) >= 2


def test_no_candidate_surviving_ep_cutoff_ends_phase(selector, config):
    result = selector.sample_move(position, engine_with_only_over_limit_moves, config)
    assert result.move is None
    assert result.exit_reason is OpeningExitReason.NO_ACCEPTABLE_CANDIDATE


def test_terminal_position_ends_without_calling_engine(selector, terminal_position):
    result = selector.next_move(terminal_position, engine_that_must_not_run, phase)
    assert result.exit_reason is OpeningExitReason.TERMINAL_POSITION
```

Add tests that every selected move is legal, supplied seeds are preserved,
explicit seed selection is independent of prior generated-session usage, and
generated-session usage penalizes a line after it is used. Define
`engine_with_only_over_limit_moves` as a `ScriptedEngine` returning two legal
opening-position evaluations with EP losses 0.09 and 0.12 for exploratory
mode; define `engine_that_must_not_run` as a fake whose `analyze()` raises
`AssertionError`. Define `terminal_position` from
`7k/5Q2/7K/8/8/8/8/8 b - - 0 1` and an ended `OpeningPhaseState` fixture.

The selector fixture uses a short two-line suite only to prove deterministic
selection; the repository dataset used by match-flow tests contains longer
lines. `OpeningMoveAudit` retains mode, seed, ECO/name/variation, source
(`suite` or `multipv_sampling`), candidate rank, EP loss, sampling weight, the full
considered-candidate list, cutoff, node budget, opening ply, planned exit ply,
sampling mode, and the experimental flag.

- [ ] **Step 2: Run selector tests and verify RED.**

Run: `uv run pytest tests/unit/test_opening_suite.py tests/unit/test_opening_exploration.py -q`

Expected: failure because the suite parser, selector, and session tracker do not exist.

- [ ] **Step 3: Implement the suite adapter and pure selector.**

Parse the YAML into immutable `OpeningLine`s and sort by stable `line_id`.
Reject malformed entries at load time with `ConfigurationError`. The selector
uses `random.Random(seed)` for family, line, exit, and sampling choices. For a
generated seed, weight each line by `line.weight / (1 + usage_count)`; for an
explicit replay seed, use the original line weights so the same seed and
configuration reproduce the same result. Validate a line with
`BoardService.view(initial_fen, moves_uci)` and skip illegal lines in stable
order. Return `NO_COMPATIBLE_LINE` when none is legal.

For MultiPV sampling, calculate each candidate's EP loss relative to the best
candidate, filter with `max_ep_loss`, and assign
`exp(-ep_loss / max(temperature, 1e-9))` weights. Sort candidate UCI before
sampling. Return all considered candidates and the selected weight in
`OpeningMoveAudit`. If the board is terminal, the candidate set is empty, or
the engine raises `EngineError`, return an explicit exit reason rather than
inventing a move.

`OpeningSession` owns a `threading.Lock` and usage counts per dataset line. It
increments usage only after a generated match successfully selects a
compatible line. It exposes a snapshot for audit/tests and never stores engine
objects.

- [ ] **Step 4: Run selector and adapter tests.**

Run: `uv run pytest tests/unit/test_opening_suite.py tests/unit/test_opening_exploration.py -q`

Expected: PASS with no timing or uncontrolled entropy dependency.

### Task 3: Store opening phase and hand off to the side policy

**Files:**

- Modify: `src/brilliant_chess/application/play_match.py`
- Modify: `src/brilliant_chess/interfaces/web/app.py`
- Modify: `src/brilliant_chess/interfaces/web/routes.py`
- Test: `tests/unit/test_play_match.py`
- Test: `tests/unit/test_opening_match_flow.py`
- Modify: `tests/fakes/stub_engine.py`

**Interfaces:**

- Consumes: `OpeningSession`, `OpeningSelector`, `MatchPolicy` including `strict_v2`, and both engine pair instances.
- Produces: immutable `MatchState` opening fields, `SelectionKind.OPENING_EXPLORATION`, and opening-aware `step_match` behavior.

- [ ] **Step 1: Write failing match-flow tests.**

```python
def test_match_stores_generated_seed_and_selected_opening(client):
    match = client.post("/api/match", json={"opening": {"mode": "exploratory"}}).json()
    assert isinstance(match["opening_seed"], int)
    assert match["opening"]["mode"] == "exploratory"


def test_opening_move_is_not_strict_or_normal(client):
    match = create_match(client, opening={"mode": "controlled", "seed": 42})
    stepped = client.post(f"/api/match/{match['match_id']}/step").json()
    assert stepped["moves"][0]["selection"] == "opening_exploration"
    assert stepped["moves"][0]["audit"] is None
    assert stepped["moves"][0]["opening_audit"]["seed"] == 42


def test_after_opening_phase_configured_policy_controls_next_move(client):
    match = create_match(client, opening={"mode": "off"}, white_policy="strict_v2")
    stepped = client.post(f"/api/match/{match['match_id']}/step").json()
    assert stepped["moves"][0]["selection"] in {"strict_v2", "near_brilliant", "fallback"}
```

Define `create_match(client, opening, white_policy="normal")` in the test
module as a direct POST helper with maximo white, iniciante black, and the
provided opening object. The existing `StubPairSession` supplies deterministic
legal moves; no engine mock is needed for the policy handoff assertion.

Add tests for terminal positions, incompatible datasets, empty sampled
candidates, legal moves, restart seed freshness, and the fact that chaotic
opening moves carry `experimental=true`.

The seed boundary uses `secrets.randbits` (or an injected equivalent) only
when the request omits a seed. Match-flow tests inject a fixed provider to
prove two omitted-seed restarts differ without relying on wall-clock timing;
an explicit seed is returned unchanged and is never replaced by entropy.

- [ ] **Step 2: Run flow tests and verify RED.**

Run: `uv run pytest tests/unit/test_play_match.py tests/unit/test_opening_match_flow.py tests/unit/test_web_api.py -q`

Expected: failure because `MatchState` has no opening phase and the route does not dispatch opening moves.

- [ ] **Step 3: Implement state and one-ply dispatch.**

Extend `MatchState` with `opening_config`, `opening_seed`, selected identity,
phase state, dataset version, and `opening_usage_snapshot`. Extend
`MatchMove` with optional `opening_audit`; keep strict `MatchAudit` untouched
for non-opening moves. Add `SelectionKind.OPENING_EXPLORATION`.

On match creation, resolve the configured default mode (`exploratory` when the
opening object is omitted) and seed through an injectable seed provider,
choose a compatible line, and store an explicit disabled/ended phase when mode
is off or no line is compatible. In
`step_match`, first check board terminal status, then request the next opening
move while the phase is active. Record it with `opening_audit`; never call
`choose_brilliant_move` or normal `play_move` for that ply. When the phase ends,
run the existing side-policy branch exactly once for the current position.

Attach one `OpeningSession` to `app.state` and close no engine from it. The
existing engine shutdown behavior remains unchanged.

- [ ] **Step 4: Run match-flow and existing API tests.**

Run: `uv run pytest tests/unit/test_play_match.py tests/unit/test_opening_match_flow.py tests/unit/test_web_api.py -q`

Expected: PASS, with explicit opening and post-opening selections.

### Task 4: Version API serialization and PGN reproduction metadata

**Files:**

- Modify: `src/brilliant_chess/interfaces/web/schemas.py`
- Modify: `src/brilliant_chess/interfaces/web/routes.py`
- Modify: `src/brilliant_chess/interfaces/web/pgn.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `tests/unit/test_match_pgn.py`
- Modify: `tests/unit/test_web_api.py`
- Modify: `frontend/src/lib/api.test.ts`

**Interfaces:**

- Consumes: opening-aware `MatchState`/`MatchMove` and v2 strict audit serialization.
- Produces: API schema version 3, typed opening request/response models, opening audit payloads, and reproducible PGN headers/comments.

- [ ] **Step 1: Write failing wire/PGN tests.**

```python
def test_match_response_exposes_opening_reproduction_metadata(client):
    payload = client.post(
        "/api/match",
        json={"opening": {"mode": "exploratory", "seed": 1234}},
    ).json()
    assert payload["schema_version"] == "3"
    assert payload["opening_seed"] == 1234
    assert payload["opening"]["dataset_version"] == "suite_v1"


def test_match_pgn_contains_opening_headers_and_comment(board, opening_state):
    text = build_match_pgn(opening_state, initial, current, standard_fen=STARTING_FEN)
    assert '[OpeningMode "exploratory"]' in text
    assert '[OpeningSeed "1234"]' in text
    assert '[OpeningDatasetVersion "suite_v1"]' in text
    assert "selection=opening_exploration" in text
    assert "source=suite" in text
```

Define `opening_state` as a `MatchState` with exploratory seed `1234`, dataset
`suite_v1`, identity `C50`/`Italian Game`/`Giuoco Piano`, a planned exit ply,
and one `opening_exploration` move carrying its audit. Reuse the existing
`initial = board.view(STARTING_FEN, ())` and a `current` view after that move
so the test exercises the real movetext path.

- [ ] **Step 2: Run wire/PGN tests and verify RED.**

Run: `uv run pytest tests/unit/test_match_pgn.py tests/unit/test_web_api.py -q`

Run: `npm test -- --run frontend/src/lib/api.test.ts`

Expected: failure because schema version and opening fields do not exist.

- [ ] **Step 3: Implement typed API and PGN output.**

Set `API_SCHEMA_VERSION = "3"`. Add `OpeningModeIn`, `OpeningConfigIn`,
`OpeningIdentityOut`, `OpeningPhaseOut`, `OpeningMoveAuditOut`, and match
response fields for seed/config/identity/phase/dataset. Add `opening_audit` to
`MatchMoveOut`; `audit` remains nullable for opening moves. Preserve the
existing `schema_version` compatibility warning in the frontend.

Add headers `RuleSetWhite`, `RuleSetBlack`, `OpeningMode`, `OpeningSeed`,
`ECO`, `Opening`, `Variation`, `OpeningExitPly`, and
`OpeningDatasetVersion`. Emit one concise key/value comment after each opening
SAN with source, seed, rank, EP loss, sampling mode, cutoff, and budget. Keep
all existing strict comments and experimental cap comments byte-compatible
where their old tests assert exact text.

- [ ] **Step 4: Run backend/frontend contract tests.**

Run: `uv run pytest tests/unit/test_match_pgn.py tests/unit/test_web_api.py -q`

Run: `npm test -- --run frontend/src/lib/api.test.ts`

Expected: PASS with schema version 3 and v1/v2/normal/opening payloads represented distinctly.

### Task 5: Add the laboratory opening selector and audit display

**Files:**

- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/lab.ts`
- Modify: `frontend/src/components/lab-parts.tsx`
- Modify: `frontend/src/pages/lab.tsx`
- Modify: `frontend/src/pages/lab.test.tsx`
- Modify: `frontend/src/components/lab-parts.test.tsx`
- Modify: `frontend/src/lib/api.test.ts`

**Interfaces:**

- Consumes: schema 3 match fields and `opening_exploration` move audits.
- Produces: “Opening variety” selector, opening summary, distinct legend mark, and preserved command layout.

- [ ] **Step 1: Write failing frontend tests.**

```tsx
it("defaults the Mesa opening selector to Exploratory", async () => {
  render(<LabPage />)
  expect(await screen.findByRole("combobox", { name: "Variedade de abertura" })).toHaveTextContent(
    "Exploratory",
  )
})

it("shows opening seed and phase without changing command hierarchy", async () => {
  render(<LabPage />)
  expect(await screen.findByText(/seed 1234/i)).toBeInTheDocument()
  expect(screen.getByRole("group", { name: "Ação principal do duelo" })).toHaveClass("grid")
  expect(screen.getByRole("group", { name: "Comandos auxiliares do duelo" })).toHaveClass("grid-cols-4")
})
```

Add a component test that `SelectionLegend` includes `opening_exploration` and
that `SelectionMark` uses a distinct non-brilliant tone/glifo. Extend fixtures
with the schema 3 opening fields rather than replacing the current FEN/PGN
test setup.

- [ ] **Step 2: Run the frontend tests and verify RED.**

Run: `npm test -- --run frontend/src/pages/lab.test.tsx frontend/src/components/lab-parts.test.tsx frontend/src/lib/api.test.ts`

Expected: failure because the opening selector/types/legend do not exist.

- [ ] **Step 3: Implement the smallest UI changes.**

Add `OpeningMode`, opening metadata, and opening audit types to `api.ts`; send
`opening: {mode, seed}` from `createMatch`. Add an “Opening variety” select to
the existing Mesa register, defaulting to `exploratory` and disabled after
match creation. Add opening seed/identity/phase text near the existing status
and audit areas. Add a separate `opening_exploration` entry to selection order,
metadata, legend, counts, `Verdict`, and `SelectionMark`.

Change the laboratory's strict-side default from `strict_v1` to `strict_v2`;
keep `strict_v1` available as an explicit comparison option in both the API
and selector. The opening selector remains a match-level setting and does not
alter either side policy or its thresholds after the opening phase.

Keep the primary command group as one full-width button and the secondary group
as exactly four buttons. Restart clears the old match and causes the next
create request to omit the old seed. Do not touch the unrelated PGN/FEN
analysis additions except where schema type compilation requires it.

- [ ] **Step 4: Run frontend tests and type/build checks.**

Run: `npm test -- --run frontend/src/pages/lab.test.tsx frontend/src/components/lab-parts.test.tsx frontend/src/lib/api.test.ts`

Run: `npm run typecheck`

Run: `npm run build`

Expected: PASS, with the four-button layout test still green.

### Task 6: Document dataset, modes, and verify the complete delivery

**Files:**

- Modify: `docs/domain-rules.md`
- Modify: `docs/architecture.md`
- Modify: `docs/testing.md`
- Modify: `README.md`
- Create: `docs/decisions/0010-opening-exploration.md`

- [ ] **Step 1: Add documentation checks before prose changes.**

```python
def test_opening_modes_are_all_serializable():
    assert {mode.value for mode in OpeningMode} == {"off", "controlled", "exploratory", "chaotic"}
```

- [ ] **Step 2: Run the check and then document the shipped behavior.**

Run: `uv run pytest tests/unit/test_opening_models.py tests/unit/test_opening_exploration.py -q`

Document the four modes and exact defaults, seed/replay rules, session novelty,
dataset provenance/license, API schema 3, PGN headers, handoff semantics,
terminal/empty-set behavior, and the preserved local fair-play boundary. ADR
0010 records why opening selection is match-level and separate from side
policies.

- [ ] **Step 3: Run the complete verification suite.**

Run: `uv run pytest`

Run: `uv run ruff check .`

Run: `uv run ruff format --check .`

Run: `uv run mypy src`

Run from `frontend/`: `npm test`

Run from `frontend/`: `npm run typecheck`

Run from `frontend/`: `npm run build`

Run: `uv run pytest -m slow`

Expected: all available checks pass; slow tests may skip only when Stockfish is unavailable.
