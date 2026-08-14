# Task 2 report — typed exchange traces behind the board port

Date: 2026-08-14

## Scope

Implemented Task 2 in the board port/adapter only:

- `src/brilliant_chess/domain/exchange.py`
- `src/brilliant_chess/ports/board.py`
- `src/brilliant_chess/adapters/board/service.py`
- `tests/unit/test_board_service.py`
- `tests/unit/test_ports.py`

Preserved unrelated uncommitted frontend/web/PGN work. Did not touch routes, frontend, or opening code.

## TDD log

### RED

Added failing tests first for:

- regression trace with `b5c6` followed by `bxc6`
- x-ray recapture sequence `e6d5`, `d1d5`
- legal empty-trace behavior when no acceptance exists
- illegal candidate returns no traces
- deterministic UCI ordering of acceptance branches
- typed snapshots/captured-piece payload free of `python-chess`
- board port type signature for `exchange_lines`

Command:

```bash
uv run pytest tests/unit/test_board_service.py tests/unit/test_ports.py -q
```

Output:

```text
.............FFFFFF.....F                                                [100%]
================================== FAILURES ===================================
__________ test_exchange_trace_contains_candidate_and_bxc6_recapture __________

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F566FF0>

    def test_exchange_trace_contains_candidate_and_bxc6_recapture(board):
>       traces = board.exchange_lines(REGRESSION_FEN, (), "b5c6", max_plies=4)
                 ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:118: AttributeError
_________________ test_exchange_trace_follows_xray_recapture __________________

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F566CC0>

    def test_exchange_trace_follows_xray_recapture(board):
>       traces = board.exchange_lines(
                 ^^^^^^^^^^^^^^^^^^^^
            "7k/8/4p3/3p4/8/8/3Q4/3R2K1 w - - 0 1",
            (),
            "d2d5",
            max_plies=4,
        )
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:128: AttributeError
_ test_exchange_lines_returns_empty_acceptance_trace_for_legal_unaccepted_candidate _

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F565370>

    def test_exchange_lines_returns_empty_acceptance_trace_for_legal_unaccepted_candidate(board):
>       traces = board.exchange_lines(STARTING_FEN, (), "e2e4", max_plies=4)
                 ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:141: AttributeError
_________ test_exchange_lines_returns_no_trace_for_illegal_candidate __________

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F566F30>

    def test_exchange_lines_returns_no_trace_for_illegal_candidate(board):
>       assert board.exchange_lines(STARTING_FEN, (), "e2e5", max_plies=4) == ()
               ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:154: AttributeError
____________________ test_exchange_lines_are_sorted_by_uci ____________________

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F59E060>

    def test_exchange_lines_are_sorted_by_uci(board):
>       traces = board.exchange_lines("7k/8/3p1p2/3P4/8/8/3Q4/3R2K1 w - - 0 1", (), "d2d5", max_plies=2)
                 ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:158: AttributeError
_ test_exchange_lines_capture_snapshots_and_removed_piece_without_python_chess_objects _

board = <brilliant_chess.adapters.board.service.PythonChessBoardService object at 0x000002BB2F59E540>

    def test_exchange_lines_capture_snapshots_and_removed_piece_without_python_chess_objects(board):
>       trace = board.exchange_lines(REGRESSION_FEN, (), "b5c6", max_plies=2)[0]
                ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'PythonChessBoardService' object has no attribute 'exchange_lines'

tests\unit\test_board_service.py:163: AttributeError
____________ test_board_service_declares_typed_exchange_lines_port ____________

    def test_board_service_declares_typed_exchange_lines_port():
>       hints = get_type_hints(BoardService.exchange_lines)
                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: type object 'BoardService' has no attribute 'exchange_lines'

tests\unit\test_ports.py:91: AttributeError
=========================== short test summary info ===========================
FAILED tests/unit/test_board_service.py::test_exchange_trace_contains_candidate_and_bxc6_recapture
FAILED tests/unit/test_board_service.py::test_exchange_trace_follows_xray_recapture
FAILED tests/unit/test_board_service.py::test_exchange_lines_returns_empty_acceptance_trace_for_legal_unaccepted_candidate
FAILED tests/unit/test_board_service.py::test_exchange_lines_returns_no_trace_for_illegal_candidate
FAILED tests/unit/test_board_service.py::test_exchange_lines_are_sorted_by_uci
FAILED tests/unit/test_board_service.py::test_exchange_lines_capture_snapshots_and_removed_piece_without_python_chess_objects
FAILED tests/unit/test_ports.py::test_board_service_declares_typed_exchange_lines_port
```

RED verified: failures were exactly the missing port method and missing adapter implementation.

### GREEN

Implemented:

- typed `ExchangePly` and `ExchangeTrace` using existing domain models
- `BoardService.exchange_lines(...) -> tuple[ExchangeTrace, ...]`
- python-chess-only traversal in `PythonChessBoardService`
- recursive, deterministic UCI-sorted capture branches on the candidate target square
- SAN preservation from the pre-push board state
- capture detection by comparing before/after snapshots, including en passant support
- legal no-acceptance empty trace behavior
- illegal candidate returns `()`

During GREEN I found one bad test fixture I had written for deterministic ordering: it accidentally placed a white pawn on `d5`, making `Qd2-d5` illegal. I corrected only that fixture and reran the suite.

Command:

```bash
uv run pytest tests/unit/test_board_service.py tests/unit/test_ports.py -q
```

Output:

```text
.........................                                                [100%]
```

## Design/result notes

- The adapter remains the only `python-chess` traversal boundary.
- Returned trace values use only:
  - `PositionSnapshot`
  - `Move`
  - `Piece`
  - tuples/strings
- No `chess.Board`, `chess.Move`, or adapter-only types leak through the port.
- The legal empty-trace case is preserved so downstream evaluation can distinguish “declined/no acceptance” from “illegal candidate”.
- Branch ordering is deterministic by UCI at every capture choice.

## Self-review

Reviewed diffs for only the five task files.

Checked for accidental collisions with existing sacrifice evidence:

- existing `SacrificeEvidence.acceptance_moves: tuple[str, ...]` is untouched
- new typed exchange traces live in `domain/exchange.py`
- no routes/frontend/opening files changed

## Files changed

- `src/brilliant_chess/domain/exchange.py`
- `src/brilliant_chess/ports/board.py`
- `src/brilliant_chess/adapters/board/service.py`
- `tests/unit/test_board_service.py`
- `tests/unit/test_ports.py`

## Concerns

- `ExchangeTrace` defaults now use optional snapshots/candidate so `ExchangeEvidence.trace` can still use `default_factory=ExchangeTrace`. That keeps compatibility, but downstream strict_v2 consumers should treat those fields as populated only when a real trace was produced.
