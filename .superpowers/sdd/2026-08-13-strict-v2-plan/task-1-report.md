# Task 1 report — strict_v2 pure evidence, thresholds, and gate contracts

Date: 2026-08-14

Scope implemented:

- Added pure-domain `exchange.py` with `ExchangeDisposition`, `ExchangePly`, `ExchangeTrace`, and `ExchangeEvidence`.
- Added pure-domain `non_obviousness.py` with `NonObviousnessCondition` and `NonObviousnessEvidence`.
- Extended `SacrificeEvidence` with optional `exchange`.
- Added v2 thresholds to `SacrificeThresholds` and a new `NonObviousnessThresholds` block on `RuleSet`.
- Added `GateId.NON_OBVIOUS`.
- Added `gate_sacrifice_v2()` and `gate_non_obviousness()`.
- Kept `strict_v1` at seven gates and appended the eighth mandatory gate only for `RuleSet(id="strict_v2")`.
- Updated sacrifice scoring to prefer `exchange.net_material_concession` when present.

TDD log:

1. RED: wrote the new tests first in:
   - `tests/unit/test_sacrifice.py`
   - `tests/unit/test_gates.py`
   - `tests/unit/test_scoring.py`
2. RED verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Result: failed during collection with `ModuleNotFoundError` for:
   - `brilliant_chess.domain.exchange`
   - `brilliant_chess.domain.non_obviousness` (indirectly blocked by the first missing import set)

   This was the expected failure mode for the new strict_v2 types/gates.
3. GREEN implementation:
   - created the two pure domain modules
   - wired new thresholds and optional evidence into existing domain contracts
   - added v2-only gate evaluation behavior
   - preserved v1 gate behavior and result shape
4. GREEN verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Result: `45 passed, 1 skipped`
5. Additional relevant regression verification:

   `uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_edge_cases.py tests/unit/test_match_pgn.py -q`

   Result: `40 passed`

Key implementation notes:

- The clean-trade rejection path in `gate_sacrifice_v2()` uses the required Portuguese explanation:
  - `troca limpa de material aproximadamente igual`
  - `não satisfaz o portão de sacrifício`
- Absent or indeterminate non-obviousness evidence fails the mandatory v2 gate.
- `decide()` still derives `selectable` only from `all_gates_passed()`.
- `strict_v1` remains shape-compatible; the test that enumerates gate ids now explicitly skips the v2-only gate when validating v1 output.

Files changed:

- `src/brilliant_chess/domain/exchange.py`
- `src/brilliant_chess/domain/non_obviousness.py`
- `src/brilliant_chess/domain/values.py`
- `src/brilliant_chess/domain/sacrifice.py`
- `src/brilliant_chess/domain/rule_set.py`
- `src/brilliant_chess/domain/gates.py`
- `src/brilliant_chess/domain/scoring.py`
- `tests/unit/test_sacrifice.py`
- `tests/unit/test_gates.py`
- `tests/unit/test_scoring.py`

Self-review summary:

- Confirmed no routes, frontend, opening code, or unrelated user changes were modified.
- Confirmed new domain modules stay on the domain side of the import boundary.
- Confirmed `strict_v1` still returns seven gates and `strict_v2` returns eight.
- Confirmed scoring change is narrowly scoped to exchange concession preference.

Concerns / follow-up notes:

- `bootstrap/config.py` was intentionally left unchanged because this task was scoped to pure-domain contracts only. A later task will need to extend validated config/YAML wiring before external strict_v2 configuration can flow through that boundary.

## Fix round 1 — reviewer issues on v2 exchange rejection

Date: 2026-08-14

Reviewer issues addressed:

- High: `gate_sacrifice_v2()` now rejects negative v2 exchange classes beyond clean equal trades, including favorable trades, obvious recaptures, and temporary/recovered offers, by both explicit flags and their corresponding `ExchangeDisposition` values.
- Medium: added focused rejection tests for favorable trades, obvious recaptures beyond equal-trade tolerance, and temporary offers with complete evidence.

Files changed in fix round:

- `src/brilliant_chess/domain/gates.py`
- `tests/unit/test_gates.py`

TDD log for fix round:

1. RED: added failing tests:
   - `test_v2_gate_rejects_favorable_trade_even_with_large_concession`
   - `test_v2_gate_rejects_obvious_recapture_beyond_equal_trade_tolerance`
   - `test_v2_gate_rejects_temporary_offer_with_complete_evidence`
2. RED verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Output summary:

   - Exit code: `1`
   - Result: `...FFF...`
   - Failures:
     - `test_v2_gate_rejects_favorable_trade_even_with_large_concession`
     - `test_v2_gate_rejects_obvious_recapture_beyond_equal_trade_tolerance`
     - `test_v2_gate_rejects_temporary_offer_with_complete_evidence`
   - Failure mode: `gate_sacrifice_v2()` returned `GateStatus.PASSED` for all three negative exchange cases.

3. GREEN implementation:
   - imported `ExchangeDisposition` into `gates.py`
   - added an explicit negative-disposition set for:
     - `CLEAN_EQUAL_TRADE`
     - `FAVORABLE_TRADE`
     - `OBVIOUS_RECAPTURE`
     - `TEMPORARY_OFFER`
   - expanded the rejection predicate to fail on:
     - `exchange.clean_trade`
     - `exchange.favorable_trade`
     - `exchange.obvious_recapture`
     - `exchange.temporary_offer`
     - matching negative `ExchangeDisposition`
     - equal-trade tolerance fallback

4. GREEN verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Output summary:

   - Exit code: `0`
   - Result: `.....................................s...........`

5. Relevant regression verification command:

   `uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_edge_cases.py tests/unit/test_match_pgn.py -q`

   Output summary:

   - Exit code: `0`
   - Result: `........................................`

6. Fresh pre-completion verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py tests/unit/test_choose_brilliant_move.py tests/unit/test_edge_cases.py tests/unit/test_match_pgn.py -q`

   Output summary:

   - Exit code: `0`
   - Result:
     - `..................................s..................................... [ 83%]`
     - `..............                                                           [100%]`

Fix-round notes:

- `strict_v1` behavior remains unchanged.
- The v2 sacrifice gate still allows genuine exchange-sacrifice acceptance paths because only the explicitly negative/recovered/favorable/obvious classes are rejected before the concession threshold check.

## Fix round 2 — reviewer issue on declined recapture

Date: 2026-08-14

Reviewer issues addressed:

- High: `gate_sacrifice_v2()` now rejects `ExchangeDisposition.DECLINED_RECAPTURE` in the same negative-disposition branch without weakening genuine exchange-sacrifice acceptance.
- Medium: added a focused rejection test covering `DECLINED_RECAPTURE` with `net_material_concession >= 1.0`.

Files changed in fix round:

- `src/brilliant_chess/domain/gates.py`
- `tests/unit/test_gates.py`

TDD log for fix round:

1. RED: added failing test:
   - `test_v2_gate_rejects_declined_recapture_with_large_concession`

2. RED verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Output summary:

   - Exit code: `1`
   - Result: `..................F...................s...........`
   - Failure:
     - `test_v2_gate_rejects_declined_recapture_with_large_concession`
   - Failure mode: `gate_sacrifice_v2()` returned `GateStatus.PASSED` for `disposicao=declined_recapture` with `concessao liquida=1.50`.

3. GREEN implementation:
   - added `ExchangeDisposition.DECLINED_RECAPTURE` to the negative disposition set in `gate_sacrifice_v2()`
   - extended the failure explanation text to mention `recaptura recusada`

4. GREEN verification command:

   `uv run pytest tests/unit/test_sacrifice.py tests/unit/test_gates.py tests/unit/test_scoring.py -q`

   Output summary:

   - Exit code: `0`
   - Result: `......................................s...........`

5. Relevant regression verification command:

   `uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_edge_cases.py tests/unit/test_match_pgn.py -q`

   Output summary:

   - Exit code: `0`
   - Result: `........................................`

Fix-round notes:

- `strict_v1` behavior remains unchanged.
- `DECLINED_RECAPTURE` now follows the same rejection path already applied to clean/favorable/obvious/temporary recovered exchanges.
