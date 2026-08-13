"""Implementacao de ``ports.board.BoardService`` com python-chess."""

from __future__ import annotations

from collections.abc import Sequence

import chess

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
