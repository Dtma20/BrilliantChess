# Task 5 — strict_v2 integration report

Status: implemented and verified on 2026-08-13.

## Delivered

- Added `config/strict_v2.yaml` without changing `strict_v1.yaml` or the normal policy.
- Added bootstrap/container resolution for both strict rule sets, including the shipped v2 fallback.
- Added `STRICT_V2` match policy and selection provenance while retaining explicit `strict_v1` selection.
- Made the laboratory strict default `strict_v2` and exposed the typed frontend contract.
- Serialized v2 audit evidence and provenance: exchange disposition (including rejected exchange evidence), non-obviousness measurements, detector version, engine/NNUE identity, and node budgets.
- Added compact v2 PGN provenance comments while leaving historical v1 comments unchanged.
- Added focused backend and frontend contract tests.

## TDD and verification

The focused tests were written first and initially failed for the missing v2 config, policy resolution, and audit fields. After implementation:

- `uv run pytest tests/unit/test_config.py tests/unit/test_web_api.py tests/unit/test_match_pgn.py tests/unit/test_play_match.py -q` — passed (62 tests).
- `npm test -- --run src/lib/api.test.ts src/lib/lab.test.ts src/components/lab-parts.test.tsx` — passed (28 tests).
- `npm test` — passed (52 tests).
- `npm run typecheck` — passed.
- `npm run lint` — passed with four existing Fast Refresh warnings in `src/components/ui/{toggle,tabs,badge,button}.tsx`.
- `uv run mypy src` — passed (53 source files).
- Focused `uv run ruff check` — passed.
- Focused `uv run ruff format --check` — passed for the clean Task 5 backend files.

The repository-wide `uv run ruff format --check .` remains blocked by pre-existing formatting in the protected dirty web/test files and the untracked plan documents: `src/brilliant_chess/interfaces/web/routes.py`, `src/brilliant_chess/interfaces/web/schemas.py`, `tests/unit/test_web_api.py`, `docs/superpowers/plans/2026-08-13-opening-exploration-plan.md`, and `docs/superpowers/plans/2026-08-13-strict-v2-plan.md`. They were not reformatted.

## Preservation and follow-up

The PGN/FEN import files, protected laboratory layout changes, analysis page/setup changes, and the existing Task 2 report remain working-tree-only. The staged shared-file hunks were audited against `HEAD` and contain only Task 5 changes. Next planned work remains opening exploration; it is intentionally not included here.

## Fix round — Luna reviewer findings

- Fallback PGN comments now derive `policy` from the moving side, preserving the historical v1 text and labeling v2 fallbacks correctly.
- The laboratory selects its seven-gate historical v1 catalog or eight-gate v2 catalog from the audit rule-set version; the protected full-width start button and four-secondary-button layout remain unchanged.
- v2 PGN comments now include compact exchange balances/sequences/flags, non-obviousness EP/rank measurements, detector and engine/NNUE identity including `binary_sha256`, and node budgets. v1 evidence comments remain gated out.
- Omitted API match policy is strict_v1 again. The laboratory initializes its strict policy from `/api/lab` with a strict_v2 fallback.

TDD regressions failed first for the hard-coded fallback, missing v2 keys, v2 API default, and global eight-gate UI; they passed after the focused fixes.

Fresh fix-round verification:

- `uv run pytest tests/unit/test_config.py tests/unit/test_web_api.py tests/unit/test_match_pgn.py tests/unit/test_play_match.py -q` — passed.
- `npm test` — passed (55 tests).
- `npm run typecheck` — passed.
- `npm run lint` — passed with the four existing Fast Refresh warnings.
