# Task 4 — strict_v2 shallow surprise evidence and selection path

Status: implemented and verified on 2026-08-13.

## Scope

Implemented the v2-only selector path while preserving the historical v1
selector path and its seven-gate behavior. The change does not modify config,
container, routes, frontend, or opening code.

Changed files:

- `src/brilliant_chess/application/choose_brilliant_move.py`
- `src/brilliant_chess/domain/gates.py`
- `src/brilliant_chess/domain/non_obviousness.py`
- `tests/unit/test_choose_brilliant_move.py`
- `tests/unit/test_non_obviousness.py`

## RED

Added the exact scripted fixtures for:

- the engine-best clean `b5c6` exchange regression;
- the shallow-obvious `e2e3` case;
- the deep-surprise `e2e3` case, outside shallow top two and confirmed rank two;
- high diagnostic score with a failed mandatory gate;
- non-obviousness OR semantics and conservative missing evidence.

Command:

```text
uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py -q
```

RED result after correcting only fixture-construction mistakes: 6 expected
failures. Selector failures reported the missing `StrictSearchBudget.shallow`
field. Non-obviousness failures reported that the gate incorrectly required
rank, EP, and shallow-obviousness predicates simultaneously.

## GREEN

Implemented:

- optional `shallow` and `shallow_multipv` budget fields after existing fields,
  preserving old positional and keyword construction;
- v2 shallow MultiPV collection before discovery/confirmation;
- fixed-budget root fallback for candidates absent from shallow MultiPV, while
  preserving `shallow_rank=None`;
- v2 exchange-aware sacrifice detection and rejected exchange evidence;
- shallow/deep rank and EP measurements, improvement, exact condition, budgets,
  detector version, engine identity including NNUE-bearing identity data;
- conservative failure when shallow/deep/budget/engine evidence is missing;
- OR semantics for EP improvement, rank improvement, and shallow top-two escape;
- separate v1/v2 audit branches, with v1 continuing to use only the historical
  destination/left-hanging detector and seven-gate result shape;
- v2 left-hanging exchanges retain valid net-concession evidence even when the
  trace records recovery of compensating material; clean/favorable/obvious and
  explicitly temporary offers remain rejected.

Focused GREEN command:

```text
uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py -q
```

Result: 23 passed.

Required Task 4 suite:

```text
uv run pytest tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py tests/unit/test_sacrifice_detector.py tests/unit/test_gates.py tests/unit/test_scoring.py -q
```

Result: passed, with the existing slow-test skip.

Additional verification:

```text
uv run pytest -q
```

Result: full Python suite passed; existing slow tests were skipped and the
existing FastAPI/httpx deprecation warning remained.

```text
uv run ruff check src/brilliant_chess/application/choose_brilliant_move.py src/brilliant_chess/domain/gates.py src/brilliant_chess/domain/non_obviousness.py tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py
uv run ruff format --check src/brilliant_chess/application/choose_brilliant_move.py src/brilliant_chess/domain/gates.py src/brilliant_chess/domain/non_obviousness.py tests/unit/test_choose_brilliant_move.py tests/unit/test_non_obviousness.py
uv run mypy src
```

Result: all passed.

## Concerns and follow-up

- Repository-wide Ruff and format checks still report unrelated pre-existing
  worktree changes in board/sacrifice/test files and the uncommitted plan
  documents. They were not modified.
- Laboratory default strict-v2 policy/configuration and API serialization are
  intentionally deferred to Task 5, per the task boundary.
