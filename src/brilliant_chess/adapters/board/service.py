"""Implementacao de ``ports.board.BoardService`` com python-chess."""

from __future__ import annotations

from collections.abc import Sequence

import chess

from brilliant_chess.domain.exchange import ExchangePly, ExchangeTrace
from brilliant_chess.domain.errors import IllegalMoveError, InvalidFenError, InvalidMoveError
from brilliant_chess.domain.material import Piece
from brilliant_chess.domain.models import Move, Position, PositionSnapshot
from brilliant_chess.domain.values import Color, GameStatus, PieceType
from brilliant_chess.ports.board import BoardView

STARTING_FEN = chess.STARTING_FEN

_PIECE_TYPES = {
    chess.PAWN: PieceType.PAWN,
    chess.KNIGHT: PieceType.KNIGHT,
    chess.BISHOP: PieceType.BISHOP,
    chess.ROOK: PieceType.ROOK,
    chess.QUEEN: PieceType.QUEEN,
    chess.KING: PieceType.KING,
}
_COLORS = {chess.WHITE: Color.WHITE, chess.BLACK: Color.BLACK}


class PythonChessBoardService:
    """Regras de xadrez confinadas a este adapter."""

    def position_after(self, initial_fen: str, moves_uci: Sequence[str]) -> Position:
        board = self._board(initial_fen, moves_uci)
        return Position.from_fen(board.fen())

    def view(self, initial_fen: str, moves_uci: Sequence[str]) -> BoardView:
        board, san = self._board_with_san(initial_fen, moves_uci)
        position = Position.from_fen(board.fen())
        return BoardView(
            position=position,
            snapshot=self._snapshot(board, position),
            legal_moves=self._legal_moves(board),
            status=self._status(board),
            is_check=board.is_check(),
            last_move_uci=board.peek().uci() if board.move_stack else None,
            move_number=board.fullmove_number,
            moves_san=san,
        )

    def normalize_move(self, position: Position, move: str) -> Move:
        """Aceita UCI ou SAN; erra explicitamente para entrada invalida ou ilegal."""
        board = self._board(position.fen, ())
        parsed = self._parse(board, move)
        if not board.is_legal(parsed):
            raise IllegalMoveError(move, position.fen)
        return Move(uci=parsed.uci(), san=board.san(parsed))

    def pv_san(self, position: Position, moves_uci: Sequence[str]) -> tuple[str, ...]:
        board = self._board(position.fen, ())
        san: list[str] = []
        for uci in moves_uci:
            candidate = chess.Move.from_uci(uci)
            if not board.is_legal(candidate):
                break
            san.append(board.san(candidate))
            board.push(candidate)
        return tuple(san)

    def exchange_lines(
        self,
        initial_fen: str,
        moves_uci: Sequence[str],
        candidate_move: str,
        max_plies: int,
    ) -> tuple[ExchangeTrace, ...]:
        board = self._board(initial_fen, moves_uci)
        root = self._snapshot(board, Position.from_fen(board.fen()))
        candidate = self._parse(board, candidate_move)
        if not board.is_legal(candidate):
            return ()
        normalized_candidate = Move(uci=candidate.uci(), san=board.san(candidate))
        board.push(candidate)
        after_candidate = self._snapshot(board, Position.from_fen(board.fen()))
        acceptance_lines = self._acceptance_lines(
            board=board,
            target_square=normalized_candidate.uci[2:4],
            remaining_plies=max_plies,
        )
        if not acceptance_lines:
            acceptance_lines = ((),)
        return tuple(
            ExchangeTrace(
                root=root,
                after_candidate=after_candidate,
                target_square=normalized_candidate.uci[2:4],
                candidate=normalized_candidate,
                acceptance_moves=line,
            )
            for line in acceptance_lines
        )

    def _board(self, initial_fen: str, moves_uci: Sequence[str]) -> chess.Board:
        return self._board_with_san(initial_fen, moves_uci)[0]

    def _board_with_san(
        self, initial_fen: str, moves_uci: Sequence[str]
    ) -> tuple[chess.Board, tuple[str, ...]]:
        try:
            board = chess.Board(initial_fen)
        except ValueError as exc:
            raise InvalidFenError(initial_fen, str(exc)) from exc
        san: list[str] = []
        for uci in moves_uci:
            move = self._parse(board, uci)
            if not board.is_legal(move):
                raise IllegalMoveError(uci, board.fen())
            san.append(board.san(move))
            board.push(move)
        return board, tuple(san)

    def _acceptance_lines(
        self,
        *,
        board: chess.Board,
        target_square: str,
        remaining_plies: int,
    ) -> tuple[tuple[ExchangePly, ...], ...]:
        if remaining_plies <= 0:
            return ()
        target = chess.parse_square(target_square)
        legal_captures = tuple(
            sorted(
                (
                    move
                    for move in board.legal_moves
                    if move.to_square == target and board.is_capture(move)
                ),
                key=chess.Move.uci,
            )
        )
        if not legal_captures:
            return ()

        lines: list[tuple[ExchangePly, ...]] = []
        for move in legal_captures:
            before = self._snapshot(board, Position.from_fen(board.fen()))
            san = board.san(move)
            board.push(move)
            after = self._snapshot(board, Position.from_fen(board.fen()))
            ply = ExchangePly(
                before=before,
                move=Move(uci=move.uci(), san=san),
                after=after,
                captured_piece=self._captured_piece(before, after, before.position.side_to_move),
            )
            tails = self._acceptance_lines(
                board=board,
                target_square=target_square,
                remaining_plies=remaining_plies - 1,
            )
            board.pop()
            if tails:
                lines.extend((ply, *tail) for tail in tails)
            else:
                lines.append((ply,))
        return tuple(lines)

    @staticmethod
    def _parse(board: chess.Board, move: str) -> chess.Move:
        text = move.strip()
        if not text:
            raise InvalidMoveError(move, "jogada vazia")
        try:
            return chess.Move.from_uci(text)
        except ValueError:
            pass
        try:
            return board.parse_san(text)
        except ValueError as exc:
            raise InvalidMoveError(move, f"nao e UCI nem SAN valido: {exc}") from exc

    @staticmethod
    def _legal_moves(board: chess.Board) -> tuple[Move, ...]:
        return tuple(Move(uci=move.uci(), san=board.san(move)) for move in board.legal_moves)

    @staticmethod
    def _snapshot(board: chess.Board, position: Position) -> PositionSnapshot:
        placement = {
            chess.square_name(square): Piece(
                color=_COLORS[piece.color], piece_type=_PIECE_TYPES[piece.piece_type]
            )
            for square, piece in board.piece_map().items()
        }
        return PositionSnapshot(
            position=position,
            placement=placement,
            halfmove_clock=board.halfmove_clock,
            fullmove_number=board.fullmove_number,
        )

    @staticmethod
    def _status(board: chess.Board) -> GameStatus:
        if board.is_checkmate():
            return GameStatus.CHECKMATE
        if board.is_stalemate():
            return GameStatus.STALEMATE
        if board.is_insufficient_material():
            return GameStatus.DRAW_INSUFFICIENT_MATERIAL
        if board.is_fifty_moves():
            return GameStatus.DRAW_FIFTY_MOVES
        if board.is_repetition(3):
            return GameStatus.DRAW_THREEFOLD_REPETITION
        return GameStatus.IN_PROGRESS

    @staticmethod
    def _captured_piece(
        before: PositionSnapshot,
        after: PositionSnapshot,
        mover: Color,
    ) -> Piece | None:
        removed = [
            piece
            for square, piece in before.placement.items()
            if piece.color is mover.opponent
            and (
                (after_piece := after.placement.get(square)) is None
                or after_piece.color is mover
                or after_piece.piece_type is not piece.piece_type
            )
        ]
        return removed[0] if removed else None
