"""Motor falso que joga sempre a primeira jogada legal em ordem UCI.

Deterministico de proposito: os testes de partida verificam o fluxo, nao a
qualidade da jogada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess

from brilliant_chess.domain.errors import EngineError
from brilliant_chess.domain.models import Move, Position
from brilliant_chess.domain.strength import EngineStrength


@dataclass
class FixedEngine:
    """Implementacao de ``ports.engine.PlayableEngine`` para testes."""

    calls: list[tuple[str, str]] = field(default_factory=list)
    fail_next: bool = False

    def play_move(self, position: Position, strength: EngineStrength) -> Move:
        if self.fail_next:
            self.fail_next = False
            raise EngineError("FixedEngine: falha injetada")
        board = chess.Board(position.fen)
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        if not moves:
            raise EngineError("Sem jogadas legais")
        chosen = moves[0]
        self.calls.append((position.fen, strength.key))
        return Move(uci=chosen.uci(), san=board.san(chosen))
