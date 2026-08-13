"""Motor falso que analisa e joga, usado nos testes da interface web.

Avalia as jogadas legais em ordem UCI com scores decrescentes: o suficiente para
exercitar ranking, setas e serializacao sem depender do Stockfish.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import chess

from brilliant_chess.domain.models import (
    AnalysisBudget,
    EngineIdentity,
    Move,
    MoveEvaluation,
    Position,
)
from brilliant_chess.domain.values import Color
from tests.fakes.fixed_engine import FixedEngine
from tests.fakes.scripted_engine import DEFAULT_IDENTITY, evaluation

_TOP_CENTIPAWNS = 100
_CENTIPAWN_STEP = 10


@dataclass
class StubEngine(FixedEngine):
    """Junta analisar e jogar no mesmo objeto, como faz o motor real."""

    closed: bool = False

    def identity(self) -> EngineIdentity:
        return DEFAULT_IDENTITY

    def close(self) -> None:
        """Espelha o ciclo de vida do motor real sem recurso externo."""
        self.closed = True

    def analyze(
        self,
        position: Position,
        budget: AnalysisBudget,
        multipv: int = 1,
        root_moves: Sequence[Move] | None = None,
    ) -> Sequence[MoveEvaluation]:
        del budget
        board = chess.Board(position.fen)
        mover = Color.WHITE if board.turn else Color.BLACK
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        if root_moves:
            wanted = {move.uci for move in root_moves}
            moves = [move for move in moves if move.uci() in wanted]
        return tuple(
            evaluation(
                move.uci(),
                mover,
                centipawns=_TOP_CENTIPAWNS - index * _CENTIPAWN_STEP,
                rank=index + 1,
                san=board.san(move),
            )
            for index, move in enumerate(moves[:multipv])
        )


class StubSession:
    """Substitui ``EngineSession`` sem iniciar processo algum."""

    def __init__(self) -> None:
        self.stub = StubEngine()
        self.closed = False

    @property
    def binary_path(self) -> Path | None:
        return Path("fake/stockfish")

    def engine(self) -> StubEngine:
        return self.stub

    def close(self) -> None:
        self.closed = True


class StubPairSession:
    """Par de motores deterministas para exercitar partidas do laboratorio."""

    def __init__(self) -> None:
        self.white = StubEngine()
        self.black = StubEngine()
        self.closed = False

    def white_engine(self) -> StubEngine:
        return self.white

    def black_engine(self) -> StubEngine:
        return self.black

    def close(self) -> None:
        self.white.close()
        self.black.close()
        self.closed = True
