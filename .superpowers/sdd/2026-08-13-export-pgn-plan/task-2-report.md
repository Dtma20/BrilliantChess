# Task 2 Report: PGN download endpoint

## Status

Implemented the local HTTP PGN export route and focused API coverage.

## Changes

- Added `GET /api/game/{game_id}/pgn` in `src/brilliant_chess/interfaces/web/routes.py`.
- The route loads the game from `GameStore`, reconstructs initial and current views through `PythonChessBoardService`, serializes with `build_pgn`, and returns `application/x-chess-pgn` with the requested attachment filename.
- Kept the operation inside `translated_errors()`, preserving the existing 400 response contract for unknown or expired games.
- Added API tests covering attachment metadata and unfinished games, checkmate result `1-0`, and custom FEN `SetUp`/`FEN` headers.

## Verification

- `uv run pytest tests/unit/test_web_api.py -k pgn -v`: 3 passed.
- `uv run pytest tests/unit/test_web_api.py -v`: 18 passed.
- `uv run ruff check src/brilliant_chess/interfaces/web/routes.py tests/unit/test_web_api.py`: passed.
- `uv run ruff format --check src/brilliant_chess/interfaces/web/routes.py tests/unit/test_web_api.py`: passed.
- `git diff --check`: passed.

## Scope and concerns

- No new dependencies.
- Local-only behavior; no third-party live-game integration or external calls added.
- The repository currently presents its project files as untracked in Git; only the two requested implementation/test files and this report were staged for the commit.
- Pytest emits the existing Starlette `httpx` deprecation warning; it does not affect test results and was not changed because dependency changes are out of scope.
