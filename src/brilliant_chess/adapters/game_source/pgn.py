"""Leitura da linha principal de um PGN local com python-chess."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import chess.pgn

from brilliant_chess.domain.errors import GameSourceError


@dataclass(frozen=True)
class ParsedPgn:
    initial_fen: str
    moves_uci: tuple[str, ...]
    moves_san: tuple[str, ...]


def parse_pgn(text: str) -> ParsedPgn:
    game = chess.pgn.read_game(StringIO(text))
    if game is None:
        raise GameSourceError("PGN vazio ou sem partida")
    if game.errors:
        raise GameSourceError(f"PGN corrompido: {game.errors[0]}")

    board = game.board()
    initial_fen = board.fen()
    moves_uci: list[str] = []
    moves_san: list[str] = []
    for move in game.mainline_moves():
        moves_uci.append(move.uci())
        moves_san.append(board.san(move))
        board.push(move)
    if not moves_uci:
        raise GameSourceError("PGN nao possui lances")
    return ParsedPgn(initial_fen, tuple(moves_uci), tuple(moves_san))
